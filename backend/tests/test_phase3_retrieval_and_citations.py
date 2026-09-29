import pytest
from typing import List
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
from backend.tests.evaluation.corpus import get_evaluation_corpus
import tempfile
import shutil

class MockLLM(BaseLLM):
    def __init__(self, canned_response: str = "This is a grounded answer."):
        self.canned_response = canned_response
        self.last_prompt = ""
        self.last_system_prompt = ""
        self.fail = False

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if self.fail:
            raise RuntimeError("Simulated LLM crash")
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return self.canned_response

    def stream(self, prompt: str, system_prompt: str = ""):
        if self.fail:
            raise RuntimeError("Simulated LLM crash")
        yield self.canned_response

# 1. Test BM25 Retriever
def test_bm25_retriever():
    bm25 = BM25Retriever()
    chunk1 = DocumentChunk(
        chunk_id="c1",
        content="Deadlocks require mutual exclusion, hold and wait, no preemption, circular wait.",
        metadata=ChunkMetadata(
            document_id="d1",
            workspace_id="ws1",
            source_type=SourceType.PDF,
            source_name="os.pdf",
            section_title="Deadlock Conditions"
        )
    )
    chunk2 = DocumentChunk(
        chunk_id="c2",
        content="TCP three-way handshake uses SYN, SYN-ACK, and ACK packets.",
        metadata=ChunkMetadata(
            document_id="d2",
            workspace_id="ws1",
            source_type=SourceType.TXT,
            source_name="tcp.txt"
        )
    )
    bm25.index_chunks([chunk1, chunk2])

    # Search for deadlock
    results = bm25.search("deadlock conditions", top_k=5)
    assert len(results) > 0
    assert results[0][0].chunk_id == "c1"
    assert results[0][1] > 0.0

    # Search with workspace filter
    res_other = bm25.search("deadlock", filters={"workspace_id": "other_ws"})
    assert len(res_other) == 0

    # Remove document
    bm25.remove_document("d1")
    res_after = bm25.search("deadlock")
    assert len(res_after) == 0

# 2. Test Fusion (Reciprocal Rank Fusion)
def test_fusion_logic():
    c1 = DocumentChunk(chunk_id="c1", content="Text 1", metadata=ChunkMetadata(document_id="d1", source_type=SourceType.TXT, source_name="t1"))
    c2 = DocumentChunk(chunk_id="c2", content="Text 2", metadata=ChunkMetadata(document_id="d2", source_type=SourceType.TXT, source_name="t2"))
    
    # Mock dense & bm25
    class DummyRetriever:
        def retrieve(self, query: str, top_k: int = 5, filters=None):
            return [(c1, 0.9), (c2, 0.5)]
    class DummyBM25:
        def search(self, query: str, top_k: int = 5, filters=None):
            return [(c2, 0.95), (c1, 0.2)]

    hybrid = HybridRetriever(
        dense_retriever=DummyRetriever(),
        keyword_retriever=DummyBM25(),
        candidate_k=5,
        rrf_k=60
    )
    fused = hybrid._reciprocal_rank_fusion(
        dense_results=[(c1, 0.9), (c2, 0.5)],
        bm25_results=[(c2, 0.95), (c1, 0.2)]
    )
    assert len(fused) == 2
    # Both chunks are present with normalized scores
    assert 0.0 <= fused[0][1] <= 1.0
    assert 0.0 <= fused[1][1] <= 1.0

# 3. Test Hybrid Retriever Fallback
def test_hybrid_fallback():
    c1 = DocumentChunk(chunk_id="c1", content="Text 1", metadata=ChunkMetadata(document_id="d1", source_type=SourceType.TXT, source_name="t1"))
    
    class FailingRetriever:
        def retrieve(self, query: str, top_k: int = 5, filters=None):
            raise RuntimeError("Dense store offline")

    class WorkingBM25:
        def search(self, query: str, top_k: int = 5, filters=None):
            return [(c1, 0.85)]

    hybrid = HybridRetriever(
        dense_retriever=FailingRetriever(),
        keyword_retriever=WorkingBM25()
    )
    # When dense fails, BM25 fallback kicks in
    results = hybrid.retrieve("query")
    assert len(results) == 1
    assert results[0][0].chunk_id == "c1"

# 4. Test Reranker & Fallback
def test_reranker_and_fallback():
    c1 = DocumentChunk(chunk_id="c1", content="Operating system deadlocks", metadata=ChunkMetadata(document_id="d1", source_type=SourceType.PDF, source_name="os.pdf", section_title="Deadlocks"))
    c2 = DocumentChunk(chunk_id="c2", content="Baking chocolate soufflé recipe", metadata=ChunkMetadata(document_id="d2", source_type=SourceType.TXT, source_name="recipes.txt"))

    # Force fallback mode
    reranker = CrossEncoderReranker(enabled=False)
    candidates = [(c2, 0.6), (c1, 0.5)]

    reranked = reranker.rerank(query="deadlocks operating systems", candidates=candidates, top_k=2)
    assert len(reranked) == 2
    # c1 has high token and title overlap, so fallback reranker should promote c1 to top rank
    assert reranked[0][0].chunk_id == "c1"
    assert reranked[0][1] > reranked[1][1]

# 5. Test Query Rewriting & Fallback
def test_query_rewriter_and_fallback():
    mock_llm = MockLLM(canned_response="What are the conditions for deadlock?")
    rewriter = ConversationalQueryRewriter(llm=mock_llm)

    history = [
        ChatTurn(role="user", content="What is deadlock?"),
        ChatTurn(role="assistant", content="Deadlock is a resource conflict.")
    ]
    rewritten = rewriter.rewrite("What are its conditions?", history)
    assert rewritten == "What are the conditions for deadlock?"

    # Fallback on LLM failure
    mock_llm.fail = True
    fallback_query = rewriter.rewrite("What are its conditions?", history)
    assert fallback_query == "What are its conditions?"

# 6. Test Context Selection & Deduplication
def test_context_selection():
    selector = ContextSelector(min_relevance_score=0.2, max_context_chunks=2, overlap_threshold=0.8)
    
    meta = ChunkMetadata(document_id="d1", source_type=SourceType.PDF, source_name="os.pdf", page_number=24)
    c1 = DocumentChunk(chunk_id="c1", content="Deadlock condition 1 mutual exclusion", metadata=meta)
    c2 = DocumentChunk(chunk_id="c2", content="Deadlock condition 1 mutual exclusion", metadata=meta) # Exact duplicate
    c3 = DocumentChunk(chunk_id="c3", content="Low score irrelevant content", metadata=meta)
    c4 = DocumentChunk(chunk_id="c4", content="Deadlock condition 2 hold and wait", metadata=meta)

    candidates = [(c1, 0.8), (c2, 0.8), (c3, 0.1), (c4, 0.7)]
    selected = selector.select(candidates)

    # c2 dropped as duplicate, c3 dropped due to score < 0.2
    assert len(selected) == 2
    assert selected[0][0].chunk_id == "c1"
    assert selected[1][0].chunk_id == "c4"
    # Metadata preserved
    assert selected[0][0].metadata.page_number == 24

# 7. Test Insufficient Context
def test_insufficient_context():
    class EmptyRetriever:
        def retrieve(self, query: str, top_k: int = 5, filters=None):
            return []

    mock_llm = MockLLM()
    engine = RAGEngine(retriever=EmptyRetriever(), llm=mock_llm)

    req = RAGQueryRequest(question="Who is the emperor of Rome in 79 AD?")
    res = engine.query(req)

    assert not res.has_sufficient_context
    assert "do not contain enough information" in res.answer
    assert len(res.citations) == 0

# 8. Test Multi-Source Citations (PDF, XLSX, CSV, YT, Web)
def test_all_source_types_citations():
    corpus = get_evaluation_corpus()
    
    class CorpusRetriever:
        def retrieve_with_details(self, query, top_k=5, filters=None):
            # Return matching chunks for the query
            matched = []
            for c in corpus:
                if any(term in c.content.lower() for term in query.lower().split()):
                    matched.append((c, 0.85))
            return {
                "results": matched[:top_k],
                "dense_candidates": matched[:top_k],
                "bm25_candidates": matched[:top_k],
                "fused_candidates": matched[:top_k],
                "reranked_candidates": matched[:top_k],
                "retrieval_ms": 1.0,
                "fusion_ms": 0.5,
                "rerank_ms": 0.5
            }

    mock_llm = MockLLM(canned_response="According to [Source 1], backpropagation calculates gradients.")
    engine = RAGEngine(retriever=CorpusRetriever(), llm=mock_llm)

    # Test YouTube citation with timestamp
    yt_req = RAGQueryRequest(question="backpropagation calculus chain rule", top_k=2)
    yt_res = engine.query(yt_req)
    assert yt_res.has_sufficient_context
    assert len(yt_res.citations) > 0
    yt_cit = [c for c in yt_res.citations if c.source_type == SourceType.YOUTUBE][0]
    assert yt_cit.start_time == 720.0
    assert yt_cit.end_time == 785.0
    assert yt_cit.timestamp_str == "12:00 - 13:05"

    # Test PDF citation with page number
    pdf_req = RAGQueryRequest(question="deadlock mutual exclusion preemption", top_k=2)
    pdf_res = engine.query(pdf_req)
    pdf_cit = [c for c in pdf_res.citations if c.source_type == SourceType.PDF][0]
    assert pdf_cit.page_number == 24
    assert pdf_cit.file_name == "Operating_Systems_Notes.pdf"

    # Test XLSX citation with sheet and row
    xlsx_req = RAGQueryRequest(question="Priya Patel CGPA Computer_Science", top_k=2)
    xlsx_res = engine.query(xlsx_req)
    xlsx_cit = [c for c in xlsx_res.citations if c.source_type == SourceType.XLSX][0]
    assert xlsx_cit.sheet_name == "Computer_Science"
    assert xlsx_cit.row_number == 15

    # Test CSV citation with row number
    csv_req = RAGQueryRequest(question="Rahul Sharma Principal Architect", top_k=2)
    csv_res = engine.query(csv_req)
    csv_cit = [c for c in csv_res.citations if c.source_type == SourceType.CSV][0]
    assert csv_cit.row_number == 12

# 9. Test Debug Mode & Latency
def test_debug_mode_and_latency():
    class DummyDetailedRetriever:
        def retrieve_with_details(self, query, top_k=5, filters=None):
            meta = ChunkMetadata(document_id="d1", source_type=SourceType.TXT, source_name="doc.txt")
            c = DocumentChunk(chunk_id="c1", content="Some verified information.", metadata=meta)
            return {
                "results": [(c, 0.9)],
                "dense_candidates": [(c, 0.8)],
                "bm25_candidates": [(c, 0.9)],
                "fused_candidates": [(c, 0.85)],
                "reranked_candidates": [(c, 0.92)],
                "retrieval_ms": 2.0,
                "fusion_ms": 1.0,
                "rerank_ms": 1.5
            }

    mock_llm = MockLLM(canned_response="Here is the answer [Source 1].")
    engine = RAGEngine(retriever=DummyDetailedRetriever(), llm=mock_llm)

    req = RAGQueryRequest(question="tell me information", debug=True)
    res = engine.query(req)

    assert res.debug is not None
    assert "original_query" in res.debug
    assert "fused_candidates" in res.debug
    assert "reranked_candidates" in res.debug
    assert res.latency is not None
    assert "retrieval_ms" in res.latency
    assert "generation_ms" in res.latency
    assert "total_ms" in res.latency
    assert res.retrieval["retriever"] == "hybrid"
