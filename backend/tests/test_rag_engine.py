import pytest
from typing import List, Optional, Iterator
from backend.app.schemas.rag import RAGQueryRequest
from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.services.rag.engine import RAGEngine
from backend.app.services.llm.base import BaseLLM

class MockLLM(BaseLLM):
    def __init__(self, response_text: str = "This is a grounded answer citing [Source 1]."):
        self.response_text = response_text

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        return self.response_text

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        yield self.response_text

class MockRetriever(BaseRetriever):
    def __init__(self, return_chunks: bool = True):
        self.return_chunks = return_chunks

    def retrieve(self, query: str, top_k: int = 5, filters = None):
        if not self.return_chunks:
            return []
        chunk = DocumentChunk(
            chunk_id="chunk-99",
            content="Deadlock occurs when four conditions are met: mutual exclusion, hold and wait, no preemption, and circular wait.",
            metadata=ChunkMetadata(
                chunk_id="chunk-99",
                document_id="doc-os",
                source_type=SourceType.PDF,
                source_name="OS Notes.pdf",
                page_number=24
            )
        )
        return [(chunk, 0.92)]

def test_rag_engine_with_context():
    retriever = MockRetriever(return_chunks=True)
    llm = MockLLM("Deadlock requires circular wait and mutual exclusion [Source 1].")
    engine = RAGEngine(retriever=retriever, llm=llm)

    req = RAGQueryRequest(question="What causes deadlock?")
    resp = engine.query(req)

    assert resp.has_sufficient_context is True
    assert len(resp.citations) == 1
    assert resp.citations[0].source_title == "OS Notes.pdf"
    assert resp.citations[0].page_number == 24
    assert resp.retrieved_count == 1
    assert "circular wait" in resp.answer

def test_rag_engine_insufficient_context():
    retriever = MockRetriever(return_chunks=False)
    llm = MockLLM()
    engine = RAGEngine(retriever=retriever, llm=llm)

    req = RAGQueryRequest(question="What is quantum tunneling?")
    resp = engine.query(req)

    assert resp.has_sufficient_context is False
    assert len(resp.citations) == 0
    assert "do not contain enough information" in resp.answer
