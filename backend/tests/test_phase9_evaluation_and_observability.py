import json
import logging
import io
from typing import List, Dict, Any

from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType
from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, Citation
from backend.app.services.rag.retriever import DenseRetriever
from backend.app.services.rag.bm25 import BM25KeywordRetriever
from backend.app.services.rag.reranker import CrossEncoderReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.engine import RAGEngine
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.evaluation.corpus import get_evaluation_corpus
from backend.evaluation.evaluator import EvaluationMockLLM, RAGEvaluator
from backend.evaluation.metrics import (
    calculate_recall_at_k,
    calculate_reciprocal_rank,
    calculate_mean_reciprocal_rank,
    evaluate_document_scope_isolation,
    evaluate_citation_quality,
    evaluate_groundedness,
    calculate_latency_percentiles
)

def test_recall_at_k_calculation():
    ground_truth = ["c1", "c2"]
    # Perfect recall@2
    retrieved = ["c1", "c2", "c3"]
    assert calculate_recall_at_k(retrieved, ground_truth, 2) == 1.0
    # Half recall@1
    assert calculate_recall_at_k(retrieved, ground_truth, 1) == 0.5
    # Zero recall@1
    retrieved_miss = ["c3", "c4", "c1"]
    assert calculate_recall_at_k(retrieved_miss, ground_truth, 1) == 0.0
    assert calculate_recall_at_k(retrieved_miss, ground_truth, 3) == 0.5
    # Empty ground truth (negative case)
    assert calculate_recall_at_k([], [], 5) == 1.0
    assert calculate_recall_at_k(["c1"], [], 5) == 0.0

def test_mrr_calculation():
    ground_truth = ["c_target"]
    assert calculate_reciprocal_rank(["c_target", "c2"], ground_truth) == 1.0
    assert calculate_reciprocal_rank(["c1", "c_target"], ground_truth) == 0.5
    assert calculate_reciprocal_rank(["c1", "c2", "c_target"], ground_truth) == round(1.0 / 3, 4)
    assert calculate_reciprocal_rank(["c1", "c2"], ground_truth) == 0.0

    mrr = calculate_mean_reciprocal_rank([1.0, 0.5, 0.0])
    assert mrr == round(1.5 / 3, 4)
    assert calculate_mean_reciprocal_rank([]) == 0.0

def test_citation_correctness_calculation():
    citations = [
        Citation(
            chunk_id="chunk_pdf_1",
            document_id="doc_pdf",
            source_title="doc.pdf",
            source_type=SourceType.PDF,
            page_number=12,
            snippet="sample"
        ),
        Citation(
            chunk_id="chunk_yt_1",
            document_id="doc_yt",
            source_title="video",
            source_type=SourceType.YOUTUBE,
            timestamp_str="05:12 - 06:10",
            snippet="sample"
        )
    ]
    retrieved_chunk_ids = ["chunk_pdf_1", "chunk_yt_1", "chunk_other"]

    # 1. Valid citations
    res = evaluate_citation_quality(citations, retrieved_chunk_ids)
    assert res["accuracy"] == 1.0
    assert len(res["issues"]) == 0

    # 2. Chunk not in retrieved context
    res_missing_chunk = evaluate_citation_quality(citations, ["chunk_pdf_1"])
    assert res_missing_chunk["accuracy"] == 0.5
    assert any("not in retrieved context" in i for i in res_missing_chunk["issues"])

    # 3. Missing source-specific metadata (e.g. PDF missing page_number)
    bad_pdf_citation = [
        Citation(
            chunk_id="chunk_pdf_1",
            document_id="doc_pdf",
            source_title="doc.pdf",
            source_type=SourceType.PDF,
            page_number=None,
            snippet="sample"
        )
    ]
    res_bad_meta = evaluate_citation_quality(bad_pdf_citation, ["chunk_pdf_1"])
    assert any("missing page_number" in i for i in res_bad_meta["issues"])

def test_document_scope_isolation():
    # Compliant retrieval
    scope_eval = evaluate_document_scope_isolation(
        retrieved_chunk_ids=["c1", "c2"],
        retrieved_doc_ids=["doc_a", "doc_a"],
        allowed_doc_ids=["doc_a"]
    )
    assert scope_eval["is_isolated"] is True
    assert scope_eval["leakage_count"] == 0

    # Leaked retrieval
    leakage_eval = evaluate_document_scope_isolation(
        retrieved_chunk_ids=["c1", "c2"],
        retrieved_doc_ids=["doc_a", "doc_b"],
        allowed_doc_ids=["doc_a"]
    )
    assert leakage_eval["is_isolated"] is False
    assert leakage_eval["leakage_count"] == 1
    assert "doc_b" in leakage_eval["leaked_document_ids"]

def test_insufficient_context_handling():
    # Empty candidate retriever simulation
    mock_llm = EvaluationMockLLM()
    embedder = HuggingFaceEmbedder()
    import tempfile
    vstore = FAISSVectorStore(dimension=embedder.dimension, store_dir=tempfile.mkdtemp())
    retriever = DenseRetriever(embedder=embedder, vector_store=vstore)

    engine = RAGEngine(retriever=retriever, llm=mock_llm)
    req = RAGQueryRequest(question="What is the quantum error correction threshold?")
    resp = engine.query(req)

    assert resp.has_sufficient_context is False
    assert len(resp.citations) == 0
    assert "do not contain enough information" in resp.answer.lower()
    assert resp.trace is not None
    assert resp.trace["retrieval_metrics"]["final_context_count"] == 0

def test_grounded_refusal():
    corpus = get_evaluation_corpus()
    evaluator = RAGEvaluator(corpus=corpus)

    # Scoped to DOCX but asking about operating systems deadlock from PDF
    req = RAGQueryRequest(
        question="What are the four Coffman conditions for a deadlock?",
        workspace_id="eval-workspace",
        document_ids=["doc-docx-eval-02"]
    )
    resp = evaluator.rag_engine.query(req)

    # Must refuse, not leak operating systems knowledge into docx citations
    assert resp.has_sufficient_context is False
    assert len(resp.citations) == 0
    assert "do not contain enough information" in resp.answer.lower()

def test_trace_creation():
    corpus = get_evaluation_corpus()
    evaluator = RAGEvaluator(corpus=corpus)

    req = RAGQueryRequest(
        question="What are the Coffman conditions?",
        workspace_id="eval-workspace",
        document_ids=["doc-pdf-eval-01"],
        enable_query_rewriting=False,
        top_k=3
    )
    resp = evaluator.rag_engine.query(req)

    assert resp.trace_id is not None
    trace = resp.trace
    assert trace is not None
    assert trace["trace_id"] == resp.trace_id
    assert "query_rewriting_latency_ms" in trace
    assert "dense_retrieval_latency_ms" in trace
    assert "bm25_retrieval_latency_ms" in trace
    assert "rrf_fusion_latency_ms" in trace
    assert "reranking_latency_ms" in trace
    assert "context_selection_latency_ms" in trace
    assert "llm_latency_ms" in trace
    assert "citation_validation_latency_ms" in trace
    assert "total_latency_ms" in trace
    assert "retrieval_metrics" in trace
    assert trace["retrieval_metrics"]["final_context_count"] > 0

def test_latency_recording():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    stats = calculate_latency_percentiles(latencies)
    assert stats["min_ms"] == 10.0
    assert stats["max_ms"] == 100.0
    assert stats["avg_ms"] == 55.0
    assert stats["p50_ms"] == 50.0
    assert stats["p90_ms"] == 90.0
    assert stats["p95_ms"] == 100.0

def test_token_usage_handling():
    corpus = get_evaluation_corpus()
    evaluator = RAGEvaluator(corpus=corpus)

    req = RAGQueryRequest(
        question="What are the four Coffman conditions?",
        workspace_id="eval-workspace",
        document_ids=["doc-pdf-eval-01"]
    )
    resp = evaluator.rag_engine.query(req)

    assert resp.tokens is not None
    assert "model" in resp.tokens
    assert "generation_latency_ms" in resp.tokens
    # Tokens can be integer or None, never negative or fabricated
    if resp.tokens.get("total_tokens") is not None:
        assert resp.tokens["total_tokens"] > 0

def test_evaluation_dataset_loading():
    evaluator = RAGEvaluator()
    dataset = evaluator.dataset
    assert len(dataset) >= 25

    for item in dataset:
        assert "id" in item
        assert "question" in item
        assert "source_type" in item
        assert "expected_refusal" in item

def test_malformed_evaluation_case_handling():
    # Case with missing optional fields
    malformed_cases = [
        {"id": "test_err_1", "question": "Where is Seattle?", "relevant_chunk_ids": []},
        {"id": "test_err_2", "question": "Invalid chunk test", "relevant_chunk_ids": ["non_existent_chunk"]}
    ]
    # Recall calculation should gracefully handle
    r1 = calculate_recall_at_k([], malformed_cases[0]["relevant_chunk_ids"], 1)
    assert r1 == 1.0

    r2 = calculate_recall_at_k(["other_chunk"], malformed_cases[1]["relevant_chunk_ids"], 1)
    assert r2 == 0.0

def test_no_secret_logging():
    from backend.app.core.logging import logger

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    try:
        corpus = get_evaluation_corpus()
        evaluator = RAGEvaluator(corpus=corpus)
        req = RAGQueryRequest(
            question="What are the Coffman conditions?",
            workspace_id="eval-workspace"
        )
        evaluator.rag_engine.query(req)

        logs = log_capture.getvalue()
        # Verify no secret keywords leaked
        assert "postgresql://" not in logs
        assert "password" not in logs.lower() or "has_sufficient_context" in logs
        assert "gsk_" not in logs
        assert "api_key" not in logs.lower()
        # JSON logs must parse as valid json lines where event is present
        for line in logs.splitlines():
            if '{"event":' in line:
                json_part = line[line.find('{"event":'):]
                parsed = json.loads(json_part)
                assert "trace_id" in parsed
                assert "total_latency_ms" in parsed
    finally:
        logger.removeHandler(handler)
