import time
import pytest
import concurrent.futures
from typing import List, Dict, Any

from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType
from backend.app.schemas.rag import RAGQueryRequest, ChatTurn, Citation
from backend.app.services.rag.bm25 import BM25Retriever
from backend.app.services.rag.reranker import CrossEncoderReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.rag.query_rewriter import ConversationalQueryRewriter
from backend.app.services.rag.engine import RAGEngine
from backend.app.services.llm.base import BaseLLM
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.core.cache import BoundedLRUCache, RAGCacheManager, cache_manager
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal, engine
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.workspace_repo import WorkspaceRepository

class MockBenchLLM(BaseLLM):
    def __init__(self, answer: str = "This is a strictly grounded answer from cache tests."):
        self.answer = answer
        self.call_count = 0

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        self.call_count += 1
        return self.answer

    def stream(self, prompt: str, system_prompt: str = ""):
        self.call_count += 1
        yield self.answer


# 1. Test BoundedLRUCache Core Functions
def test_bounded_lru_cache_core():
    cache = BoundedLRUCache(maxsize=3, default_ttl_seconds=2, name="test_lru")

    # Set and Get
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert cache.get("a") == 1
    assert cache.get("b") == 2
    assert cache.size == 3
    assert cache.hits == 2
    assert cache.misses == 0

    # Eviction on exceeding maxsize (c is MRU from get? No, a and b were accessed, c is oldest)
    cache.set("d", 4)
    assert cache.size == 3
    assert cache.get("c") is None  # c was evicted
    assert cache.evictions == 1
    assert cache.misses == 1

    # Invalidation by tag
    cache.set("e", 5, tag="ws-1")
    cache.set("f", 6, tag="ws-1")
    cache.set("g", 7, tag="ws-2")
    removed = cache.invalidate_by_tag("ws-1")
    assert removed == 2
    assert cache.get("e") is None
    assert cache.get("f") is None
    assert cache.get("g") == 7

    # Invalidation by prefix
    cache.set("pre_1", 10)
    cache.set("pre_2", 20)
    cache.set("other_1", 30)
    removed_pre = cache.invalidate_by_prefix("pre_")
    assert removed_pre == 2
    assert cache.get("pre_1") is None
    assert cache.get("other_1") == 30

    # TTL Expiration
    cache.set("exp", "val", ttl_seconds=0.01)
    time.sleep(0.02)
    assert cache.get("exp") is None


# 2. Test Workspace and Document-Scope Cache Isolation (Hard Requirement)
def test_cache_workspace_and_document_scope_isolation():
    manager = RAGCacheManager()
    manager.clear_all()

    query = "What is the capital of France?"

    # Keys for different workspaces
    key_ws1 = manager.build_retrieval_cache_key("ws-1", query, ["doc-1"], None, 5)
    key_ws2 = manager.build_retrieval_cache_key("ws-2", query, ["doc-1"], None, 5)
    assert key_ws1 != key_ws2, "Cross-workspace keys must never collide"

    # Keys for different document scopes in same workspace
    key_doc1 = manager.build_retrieval_cache_key("ws-1", query, ["doc-1"], None, 5)
    key_doc2 = manager.build_retrieval_cache_key("ws-1", query, ["doc-2"], None, 5)
    key_both = manager.build_retrieval_cache_key("ws-1", query, ["doc-1", "doc-2"], None, 5)
    assert key_doc1 != key_doc2, "Different document scope keys must never collide"
    assert key_doc1 != key_both, "Single-doc vs multi-doc scope keys must never collide"

    # Answer Cache Keys
    ans_ws1 = manager.build_answer_cache_key("ws-1", query, ["doc-1"], "model-a", 0.0, 5)
    ans_ws2 = manager.build_answer_cache_key("ws-2", query, ["doc-1"], "model-a", 0.0, 5)
    ans_doc2 = manager.build_answer_cache_key("ws-1", query, ["doc-2"], "model-a", 0.0, 5)
    assert ans_ws1 != ans_ws2
    assert ans_ws1 != ans_doc2


# 3. Test Index Version Increment and Cache Invalidation
def test_index_version_invalidation():
    manager = RAGCacheManager()
    manager.clear_all()

    ws_id = "ws-test-version"
    v1 = manager.get_workspace_version(ws_id)
    assert v1 == 1

    # Populate cache tagged with ws_id
    key1 = manager.build_retrieval_cache_key(ws_id, "query", ["doc-1"], None, 5)
    manager.retrieval_cache.set(key1, {"data": "cached"}, tag=ws_id)
    assert manager.retrieval_cache.get(key1) is not None

    ans_key1 = manager.build_answer_cache_key(ws_id, "query", ["doc-1"], "model", 0.0, 5)
    manager.answer_cache.set(ans_key1, {"answer": "cached"}, tag=ws_id)
    assert manager.answer_cache.get(ans_key1) is not None

    # Trigger version increment (simulating document add/delete)
    v2 = manager.increment_workspace_version(ws_id)
    assert v2 == 2

    # Old entries are invalidated
    assert manager.retrieval_cache.get(key1) is None
    assert manager.answer_cache.get(ans_key1) is None

    # New cache key reflects v2
    key2 = manager.build_retrieval_cache_key(ws_id, "query", ["doc-1"], None, 5)
    assert "v2" in key2
    assert key1 != key2


# 4. Test Embedding Cache Hit and Speedup
def test_embedding_cache_speedup():
    embedder = HuggingFaceEmbedder()
    cache_manager.embedding_cache.clear()

    text = "Performance optimization and caching in production RAG systems."

    # First call (cold)
    t0 = time.perf_counter()
    vec1 = embedder.embed_query(text)
    t_cold = time.perf_counter() - t0

    # Second call (warm / cached)
    t1 = time.perf_counter()
    vec2 = embedder.embed_query(text)
    t_warm = time.perf_counter() - t1

    assert vec1 == vec2
    assert cache_manager.embedding_cache.hits >= 1
    # Warm call should be substantially faster
    assert t_warm <= t_cold or t_warm < 0.01


# 5. Test RAGEngine End-to-End Answer Caching
def test_rag_engine_answer_caching():
    cache_manager.clear_all()

    c1 = DocumentChunk(
        chunk_id="chunk-c1",
        content="Antigravity provides automated agentic workflow synthesis.",
        metadata=ChunkMetadata(
            document_id="doc-perf-1",
            workspace_id="ws-perf",
            source_type=SourceType.TXT,
            source_name="doc.txt"
        )
    )

    class FastRetriever:
        def retrieve_with_details(self, query, top_k=5, filters=None):
            return {
                "results": [(c1, 0.95)],
                "dense_candidates": [(c1, 0.95)],
                "bm25_candidates": [(c1, 0.9)],
                "fused_candidates": [(c1, 0.95)],
                "reranked_candidates": [(c1, 0.95)],
                "dense_ms": 1.0,
                "bm25_ms": 0.5,
                "fusion_ms": 0.1,
                "rerank_ms": 0.2,
                "retrieval_ms": 1.5
            }

    mock_llm = MockBenchLLM(answer="Antigravity synthesizes workflows [Source 1].")
    engine_inst = RAGEngine(
        retriever=FastRetriever(),
        llm=mock_llm,
        context_selector=ContextSelector(min_relevance_score=0.1)
    )

    req = RAGQueryRequest(
        question="What does Antigravity provide?",
        workspace_id="ws-perf",
        document_ids=["doc-perf-1"]
    )

    # 1. Cold query (Cache Miss)
    resp1 = engine_inst.query(req)
    assert resp1.has_sufficient_context
    assert not resp1.trace.get("cache_hit", False)
    assert mock_llm.call_count == 1

    # 2. Warm query (Cache Hit)
    resp2 = engine_inst.query(req)
    assert resp2.has_sufficient_context
    assert resp2.trace.get("cache_hit", True)
    assert resp2.trace.get("cache_stage") == "answer"
    assert resp2.answer == resp1.answer
    # Citation provenance preserved 100%
    assert len(resp2.citations) == len(resp1.citations)
    assert resp2.citations[0].chunk_id == resp1.citations[0].chunk_id
    # LLM must NOT be called again
    assert mock_llm.call_count == 1

    # 3. Modify workspace index version -> Invalidate cache
    cache_manager.increment_workspace_version("ws-perf")
    resp3 = engine_inst.query(req)
    assert not resp3.trace.get("cache_hit", False)
    # LLM called because cache was invalidated
    assert mock_llm.call_count == 2


# 6. Test Query Rewriting Caching and Coreference Detection
def test_query_rewriter_caching_and_coreference():
    cache_manager.clear_all()
    mock_llm = MockBenchLLM(answer="Standalone Deadlock Query")
    rewriter = ConversationalQueryRewriter(llm=mock_llm)

    # Completely self-contained query with history -> should bypass rewriting
    hist = [ChatTurn(role="user", content="Hello"), ChatTurn(role="assistant", content="Hi")]
    standalone = rewriter.rewrite("What are the four Coffman conditions for operating system deadlock?", hist)
    assert standalone == "What are the four Coffman conditions for operating system deadlock?"
    assert mock_llm.call_count == 0  # Bypassed LLM!

    # Conversational query with coreference -> invokes LLM and caches
    dep_query = "What are its primary symptoms?"
    res1 = rewriter.rewrite(dep_query, hist)
    assert res1 == "Standalone Deadlock Query"
    assert mock_llm.call_count == 1

    # Repeated conversational query -> hits cache
    res2 = rewriter.rewrite(dep_query, hist)
    assert res2 == "Standalone Deadlock Query"
    assert mock_llm.call_count == 1  # Served from cache!


# 7. Test Database Optimized Ready Doc ID Query
def test_database_optimized_ready_doc_query():
    db = SessionLocal()
    try:
        ws = WorkspaceRepository.get_or_create(db, workspace_id="ws-db-opt")
        # Clean existing
        existing = DocumentRepository.list_by_workspace(db, "ws-db-opt")
        for d in existing:
            DocumentRepository.delete(db, d.id)
        db.commit()

        # Create 1 ready and 1 pending document
        d1 = DocumentRepository.create(
            db, workspace_id="ws-db-opt", source_type="txt", title="Ready Doc",
            content_hash="hash-ready-1", status="ready"
        )
        d2 = DocumentRepository.create(
            db, workspace_id="ws-db-opt", source_type="txt", title="Pending Doc",
            content_hash="hash-pending-2", status="pending"
        )
        db.commit()

        # Test optimized query
        ready_ids = DocumentRepository.list_ready_ids_by_workspace(db, "ws-db-opt")
        assert len(ready_ids) == 1
        assert d1.id in ready_ids
        assert d2.id not in ready_ids
    finally:
        db.close()


# 8. Test Concurrency Load and Thread Safety
def test_concurrent_rag_queries():
    cache_manager.clear_all()
    c1 = DocumentChunk(
        chunk_id="c-conc-1",
        content="Concurrent query test chunk data.",
        metadata=ChunkMetadata(document_id="doc-conc", workspace_id="ws-conc", source_type=SourceType.TXT, source_name="t.txt")
    )

    class ThreadSafeRetriever:
        def retrieve(self, query, top_k=5, filters=None):
            return [(c1, 0.9)]

    mock_llm = MockBenchLLM(answer="Safe response under concurrency.")
    engine_inst = RAGEngine(retriever=ThreadSafeRetriever(), llm=mock_llm)

    def execute_one(i: int):
        req = RAGQueryRequest(
            question=f"Test concurrent question {i % 3}?",
            workspace_id="ws-conc",
            document_ids=["doc-conc"]
        )
        resp = engine_inst.query(req)
        return resp.has_sufficient_context, resp.answer

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(execute_one, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    assert all(r[0] is True for r in results)
    assert all("Safe response" in r[1] for r in results)
