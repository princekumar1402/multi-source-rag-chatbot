import pytest
from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType
from backend.app.schemas.rag import ChatTurn
from backend.app.services.rag.reranker import CrossEncoderReranker
from backend.app.services.rag.query_rewriter import ConversationalQueryRewriter
from backend.app.services.rag.confidence import (
    RetrievalConfidenceAssessor,
    RetrievalConfidence,
    ConfidenceLevel
)
from backend.app.services.rag.multi_query import MultiQueryRetriever
from backend.app.services.rag.adaptive import AdaptiveRetriever
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.rag.parent_child import ContextualChunkExpander
from backend.evaluation.metrics import evaluate_groundedness, calculate_recall_at_k

class MockRetriever:
    def __init__(self, candidates):
        self.candidates = candidates

    def retrieve(self, query: str, top_k: int = 5, filters=None):
        if filters and filters.get("document_ids"):
            allowed = set(filters["document_ids"])
            filtered = [(c, s) for c, s in self.candidates if c.metadata.document_id in allowed]
            return filtered[:top_k]
        return self.candidates[:top_k]

class MockLLM:
    def __init__(self, response="Mock response"):
        self.response = response
        self.model = "mock-model"

    def generate(self, prompt: str, system_prompt=None):
        return self.response

def make_chunk(chunk_id: str, doc_id: str, content: str, title: str = "Test"):
    meta = ChunkMetadata(
        document_id=doc_id,
        source_name=title,
        source_type=SourceType.TXT,
        file_name="test.txt"
    )
    return DocumentChunk(chunk_id=chunk_id, content=content, metadata=meta)

def test_reranker_stopword_resilience():
    reranker = CrossEncoderReranker()
    c_ast = make_chunk(
        "ast", "doc-1",
        "Jupiter is the largest planet in our solar system, with a mass more than two and a half times."
    )
    c_rec = make_chunk(
        "rec", "doc-2",
        "To bake a classic dark chocolate soufflé, preheat the oven to 375 degrees Fahrenheit."
    )
    query = "What baking temperature is needed for a dark chocolate soufflé and how long should it bake?"

    rescored = reranker.rerank(query, [(c_ast, 0.5), (c_rec, 0.5)], top_k=2)
    assert rescored[0][0].chunk_id == "rec", "Recipe chunk must be ranked higher than irrelevant astronomy chunk"
    assert rescored[1][0].chunk_id == "ast"

def test_query_rewriter_self_contained_vs_conversational():
    mock_llm = MockLLM(response="What are the ACID properties in DBMS?")
    rewriter = ConversationalQueryRewriter(llm=mock_llm)

    # Standalone query without pronouns
    q_standalone = "What are the ACID properties guaranteed in transaction management systems?"
    history = [ChatTurn(role="user", content="Hello"), ChatTurn(role="assistant", content="Hi")]
    rewritten = rewriter.rewrite(q_standalone, history)
    assert rewritten == q_standalone, "Standalone query must bypass LLM rewrite"

    # Conversational query with pronoun
    q_conversational = "What are its key advantages compared to the previous version?"
    rewritten_conv = rewriter.rewrite(q_conversational, history)
    assert rewritten_conv == "What are the ACID properties in DBMS?"

def test_retrieval_confidence_assessor():
    assessor = RetrievalConfidenceAssessor()
    c1 = make_chunk("c1", "d1", "Content 1")
    c2 = make_chunk("c2", "d1", "Content 2")

    # High confidence case
    high_conf = assessor.assess(
        candidates=[(c1, 0.85), (c2, 0.40)],
        dense_candidates=[(c1, 0.9), (c2, 0.5)],
        bm25_candidates=[(c1, 0.8), (c2, 0.4)]
    )
    assert high_conf.level == ConfidenceLevel.HIGH
    assert high_conf.score >= 0.65

    # Low confidence case
    low_conf = assessor.assess(
        candidates=[(c1, 0.20), (c2, 0.18)],
        dense_candidates=[(c1, 0.2)],
        bm25_candidates=[(c2, 0.1)]
    )
    assert low_conf.level == ConfidenceLevel.LOW
    assert low_conf.score < 0.35

def test_multi_query_retrieval_and_scope_isolation():
    c1 = make_chunk("c1", "doc-A", "Database indexing with B+ trees")
    c2 = make_chunk("c2", "doc-B", "Networking protocols and TCP sockets")
    mock_retriever = MockRetriever([(c1, 0.8), (c2, 0.7)])

    mq_llm = MockLLM(response="database indexing\nB+ trees storage\ntuple execution")
    mq_retriever = MultiQueryRetriever(base_retriever=mock_retriever, llm=mq_llm)

    # Test scope isolation
    scoped = mq_retriever.retrieve(
        query="Explain B+ tree indexes",
        top_k=5,
        filters={"document_ids": ["doc-A"]}
    )
    assert len(scoped) == 1
    assert scoped[0][0].metadata.document_id == "doc-A"

def test_adaptive_retrieval_routing():
    c1 = make_chunk("c1", "d1", "Operating systems virtual memory paging")
    mock_retriever = MockRetriever([(c1, 0.90)])
    rewriter = ConversationalQueryRewriter(llm=MockLLM("rewritten query"))
    adaptive = AdaptiveRetriever(
        base_retriever=mock_retriever,
        query_rewriter=rewriter
    )

    # Direct high-confidence path
    results, routing = adaptive.route_and_retrieve("What is paging in virtual memory?")
    assert routing["strategy"] == "direct_hybrid"
    assert len(results) == 1

def test_context_selector_token_budget_and_compression():
    selector = ContextSelector(max_context_chunks=5, max_tokens=15)
    c1 = make_chunk("c1", "d1", "word " * 10) # 10 tokens
    c2 = make_chunk("c2", "d1", "word " * 10) # 10 tokens -> exceeds 15 max_tokens

    selected = selector.select([(c1, 0.8), (c2, 0.7)])
    assert len(selected) == 1, "Must halt context accumulation once token budget is reached"

def test_contextual_chunk_expander_document_boundary():
    expander = ContextualChunkExpander(max_expansion_window=1)
    c1 = make_chunk("c1", "doc-1", "Introduction paragraph.")
    c2 = make_chunk("c2", "doc-1", "Detailed analysis paragraph.")
    c3 = make_chunk("c3", "doc-2", "Unrelated other document.")

    doc_chunks = {
        "doc-1": [c1, c2],
        "doc-2": [c3]
    }

    # Expand c1 -> should include c2
    expanded = expander.expand_context([(c1, 0.9)], document_chunks=doc_chunks)
    assert len(expanded) == 1
    assert "Detailed analysis paragraph." in expanded[0][0].content
    assert expanded[0][0].chunk_id == "c1"

def test_groundedness_discourse_filtering():
    context = ["The four Coffman conditions are mutual exclusion, hold and wait, no preemption, and circular wait."]
    answer = "Based on the provided sources, the four Coffman conditions are mutual exclusion, hold and wait, no preemption, and circular wait."

    res = evaluate_groundedness(answer, context)
    assert res["score"] >= 0.90, f"Expected high groundedness score after discourse filtering, got {res['score']}"
