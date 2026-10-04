import pytest
import uuid
from typing import List, Dict, Any

from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType
from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.rag.bm25 import BM25Retriever
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.rag.engine import RAGEngine

class DummyEmbedder:
    def __init__(self, dimension: int = 4):
        self.dimension = dimension

    def embed_query(self, query: str) -> List[float]:
        # Return deterministic unit vector based on query length/content
        if "quantum" in query.lower():
            return [1.0, 0.0, 0.0, 0.0]
        elif "biology" in query.lower():
            return [0.0, 1.0, 0.0, 0.0]
        return [0.5, 0.5, 0.0, 0.0]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        res = []
        for t in texts:
            if "quantum" in t.lower() or "qubit" in t.lower():
                res.append([1.0, 0.0, 0.0, 0.0])
            elif "biology" in t.lower() or "cell" in t.lower():
                res.append([0.0, 1.0, 0.0, 0.0])
            else:
                res.append([0.0, 0.0, 1.0, 0.0])
        return res

class DeterministicMockLLM:
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        if "quantum" in prompt.lower():
            return "Quantum computing operates on qubits in superposition according to [Source 1]."
        elif "cell" in prompt.lower() or "biology" in prompt.lower():
            return "Biological cells perform metabolic functions according to [Source 1]."
        return "The available knowledge base sources do not contain enough information to answer this question."

@pytest.fixture
def scoped_knowledge_base(tmp_path):
    """Builds a deterministic in-memory hybrid knowledge base with 2 distinct documents."""
    embedder = DummyEmbedder(dimension=4)
    vstore = FAISSVectorStore(dimension=4, store_dir=str(tmp_path))
    bm25 = BM25Retriever()

    doc_a_id = "doc-quantum-100"
    doc_b_id = "doc-biology-200"
    ws_id = "ws-test-scope"

    chunk_a1 = DocumentChunk(
        chunk_id="chunk-q-1",
        content="Quantum superposition enables qubits to process multiple states simultaneously.",
        metadata=ChunkMetadata(
            chunk_id="chunk-q-1",
            document_id=doc_a_id,
            workspace_id=ws_id,
            source_type=SourceType.PDF,
            source_name="Quantum Computing 101.pdf",
            page_number=1,
            chunk_index=0
        )
    )
    chunk_a2 = DocumentChunk(
        chunk_id="chunk-q-2",
        content="Entangled qubits maintain correlated quantum states across physical distances.",
        metadata=ChunkMetadata(
            chunk_id="chunk-q-2",
            document_id=doc_a_id,
            workspace_id=ws_id,
            source_type=SourceType.PDF,
            source_name="Quantum Computing 101.pdf",
            page_number=2,
            chunk_index=1
        )
    )

    chunk_b1 = DocumentChunk(
        chunk_id="chunk-b-1",
        content="Biological cell membranes regulate molecular transport and cellular metabolism.",
        metadata=ChunkMetadata(
            chunk_id="chunk-b-1",
            document_id=doc_b_id,
            workspace_id=ws_id,
            source_type=SourceType.DOCX,
            source_name="Cellular Biology.docx",
            page_number=1,
            chunk_index=0
        )
    )

    all_chunks = [chunk_a1, chunk_a2, chunk_b1]
    embeddings = embedder.embed_documents([c.content for c in all_chunks])

    vstore.add_chunks(all_chunks, embeddings)
    bm25.index_chunks(all_chunks)

    dense_retriever = DenseRetrieverWithReranker(embedder=embedder, vector_store=vstore, min_relevance_threshold=0.1)
    hybrid_retriever = HybridRetriever(
        dense_retriever=dense_retriever,
        keyword_retriever=bm25,
        reranker=None,
        dense_weight=0.5,
        bm25_weight=0.5
    )

    engine = RAGEngine(
        retriever=hybrid_retriever,
        llm=DeterministicMockLLM(),
        context_selector=ContextSelector(min_relevance_score=0.1, max_context_chunks=4)
    )

    return {
        "engine": engine,
        "vstore": vstore,
        "bm25": bm25,
        "doc_a_id": doc_a_id,
        "doc_b_id": doc_b_id,
        "ws_id": ws_id
    }

# 1. FAISS Document Filtering
def test_faiss_document_filtering(scoped_knowledge_base):
    vstore = scoped_knowledge_base["vstore"]
    doc_a = scoped_knowledge_base["doc_a_id"]
    doc_b = scoped_knowledge_base["doc_b_id"]

    # Filter by single doc A
    res_a = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=5, filters={"document_ids": [doc_a]})
    assert len(res_a) == 2
    assert all(c.metadata.document_id == doc_a for c, _ in res_a)

    # Filter by single doc B
    res_b = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=5, filters={"document_ids": [doc_b]})
    assert len(res_b) == 1
    assert res_b[0][0].metadata.document_id == doc_b

    # Filter by empty document_ids
    res_none = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=5, filters={"document_ids": []})
    assert len(res_none) == 0

# 2. BM25 Document Filtering
def test_bm25_document_filtering(scoped_knowledge_base):
    bm25 = scoped_knowledge_base["bm25"]
    doc_a = scoped_knowledge_base["doc_a_id"]
    doc_b = scoped_knowledge_base["doc_b_id"]

    # Search term 'quantum' with doc_b filter -> should return 0
    res_b = bm25.search("quantum", top_k=5, filters={"document_ids": [doc_b]})
    assert len(res_b) == 0

    # Search term 'quantum' with doc_a filter -> should return matching chunks from doc_a
    res_a = bm25.search("quantum", top_k=5, filters={"document_ids": [doc_a]})
    assert len(res_a) >= 1
    assert all(c.metadata.document_id == doc_a for c, _ in res_a)

# 3. Hybrid Retrieval with Document Filtering
def test_hybrid_document_filtering(scoped_knowledge_base):
    engine = scoped_knowledge_base["engine"]
    doc_a = scoped_knowledge_base["doc_a_id"]
    doc_b = scoped_knowledge_base["doc_b_id"]
    ws_id = scoped_knowledge_base["ws_id"]

    # Scoped to Doc A
    req_a = RAGQueryRequest(
        question="Tell me about quantum computing",
        workspace_id=ws_id,
        document_ids=[doc_a]
    )
    resp_a = engine.query(req_a)
    assert resp_a.has_sufficient_context
    assert len(resp_a.citations) > 0
    assert all(c.document_id == doc_a for c in resp_a.citations)

    # Scoped to Doc B (should NOT contain quantum information)
    req_b = RAGQueryRequest(
        question="Tell me about quantum computing",
        workspace_id=ws_id,
        document_ids=[doc_b]
    )
    resp_b = engine.query(req_b)
    # Since Doc B is about cell biology, quantum query must yield insufficient context
    assert not resp_b.has_sufficient_context or len(resp_b.citations) == 0
    if not resp_b.has_sufficient_context:
        assert "not contain enough information" in resp_b.answer
    assert all(c.document_id == doc_b for c in resp_b.citations)

# 4. Multi-Document Search Scope
def test_multi_document_search(scoped_knowledge_base):
    engine = scoped_knowledge_base["engine"]
    doc_a = scoped_knowledge_base["doc_a_id"]
    doc_b = scoped_knowledge_base["doc_b_id"]
    ws_id = scoped_knowledge_base["ws_id"]

    req_multi = RAGQueryRequest(
        question="Explain both qubits and cell membranes",
        workspace_id=ws_id,
        document_ids=[doc_a, doc_b]
    )
    resp_multi = engine.query(req_multi)
    assert resp_multi.has_sufficient_context
    doc_ids_in_citations = {c.document_id for c in resp_multi.citations}
    assert doc_ids_in_citations.issubset({doc_a, doc_b})

# 5. All-Documents Search Scope (default)
def test_all_documents_search(scoped_knowledge_base):
    engine = scoped_knowledge_base["engine"]
    ws_id = scoped_knowledge_base["ws_id"]

    req_all = RAGQueryRequest(
        question="Explain cellular metabolism and quantum states",
        workspace_id=ws_id,
        document_ids=None # None = all documents
    )
    resp_all = engine.query(req_all)
    assert resp_all.has_sufficient_context
    assert len(resp_all.citations) > 0

# 6. Workspace Isolation
def test_workspace_isolation(scoped_knowledge_base):
    vstore = scoped_knowledge_base["vstore"]
    bm25 = scoped_knowledge_base["bm25"]

    # Searching in non-existent workspace must yield 0 results
    res_faiss = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=5, filters={"workspace_id": "other-workspace"})
    assert len(res_faiss) == 0

    res_bm25 = bm25.search("quantum", top_k=5, filters={"workspace_id": "other-workspace"})
    assert len(res_bm25) == 0

# 7. Citations Isolation (Zero Cross-Document Leakage)
def test_citation_isolation_guarantee(scoped_knowledge_base):
    engine = scoped_knowledge_base["engine"]
    doc_b = scoped_knowledge_base["doc_b_id"]
    ws_id = scoped_knowledge_base["ws_id"]

    # Scoped only to Biology doc, query asked about physics
    req = RAGQueryRequest(
        question="What is a qubit in quantum superposition?",
        workspace_id=ws_id,
        document_ids=[doc_b]
    )
    resp = engine.query(req)

    # Citations MUST NOT contain doc_a under any circumstance
    for cit in resp.citations:
        assert cit.document_id == doc_b
        assert cit.document_id != scoped_knowledge_base["doc_a_id"]
