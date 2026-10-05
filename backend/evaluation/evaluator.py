import json
import time
import os
from typing import List, Dict, Any, Optional, Tuple

from backend.app.schemas.document import DocumentChunk
from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, ChatTurn
from backend.app.services.rag.retriever import DenseRetriever
from backend.app.services.rag.bm25 import BM25KeywordRetriever
from backend.app.services.rag.reranker import CrossEncoderReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.engine import RAGEngine
from backend.app.services.rag.query_rewriter import ConversationalQueryRewriter
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.llm.base import BaseLLM
from backend.evaluation.corpus import get_evaluation_corpus
from backend.evaluation.metrics import (
    calculate_recall_at_k,
    calculate_reciprocal_rank,
    calculate_mean_reciprocal_rank,
    evaluate_document_scope_isolation,
    evaluate_citation_quality,
    evaluate_groundedness,
    calculate_latency_percentiles
)

class EvaluationMockLLM(BaseLLM):
    """
    Deterministic LLM for benchmark reproducibility when external APIs are not invoked.
    If ground truth context contains expected facts, generates a grounded answer.
    If context is empty or missing, outputs standard grounded refusal.
    """
    def __init__(self, model_name: str = "eval-grounded-mock"):
        self.model = model_name

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        answer, _ = self.generate_with_metadata(prompt, system_prompt)
        return answer

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Any:
        answer, _ = self.generate_with_metadata(prompt, system_prompt)
        for token in answer.split(" "):
            yield token + " "

    def generate_with_metadata(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        # 1. Handle conversational query rewriter prompt
        if system_prompt and ("reformulator" in system_prompt or "rewrite" in system_prompt):
            for line in prompt.split("\n"):
                if line.startswith("Follow-up Question:"):
                    rewritten = line.replace("Follow-up Question:", "").strip()
                    return rewritten, {"model": self.model}
            return prompt.strip(), {"model": self.model}

        # 2. Extract question text
        user_question = ""
        if "USER QUESTION:" in prompt:
            parts = prompt.split("USER QUESTION:")
            if len(parts) > 1:
                lines = [l.strip() for l in parts[1].split("\n") if l.strip()]
                if lines:
                    user_question = lines[0].lower()

        # 3. Extract context text
        raw_context = ""
        if "CONTEXT SOURCES:" in prompt and "USER QUESTION:" in prompt:
            raw_context = prompt.split("CONTEXT SOURCES:")[1].split("USER QUESTION:")[0].strip()
        context_lower = raw_context.lower()

        # 4. Determine if context actually supports the question (anti-hallucination / groundedness)
        is_supported = False
        if raw_context and user_question:
            q_words = [
                w.strip(".,?!\"'():;") for w in user_question.split()
                if len(w) > 3 and w not in ["what", "which", "where", "explain", "describe", "compare", "between", "how", "does", "from", "with", "that", "this"]
            ]
            matched = [w for w in q_words if w in context_lower]
            ratio = (len(matched) / len(q_words)) if q_words else 0.0
            if ratio >= 0.5 and len(matched) >= 2:
                is_supported = True

        if not is_supported or not raw_context:
            refusal = "The available knowledge base sources do not contain enough information to answer this question."
            return refusal, {
                "model": self.model,
                "token_usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(refusal.split()),
                    "total_tokens": len(prompt.split()) + len(refusal.split())
                }
            }

        # Formulate concise synthesis reflecting the retrieved snippet
        summary = f"Based on the provided sources: {raw_context[:300].strip()}"
        return summary, {
            "model": self.model,
            "token_usage": {
                "prompt_tokens": len(prompt.split()),
                "completion_tokens": len(summary.split()),
                "total_tokens": len(prompt.split()) + len(summary.split())
            }
        }

class RAGEvaluator:
    """
    Orchestrates RAG benchmark evaluations:
    - Multi-configuration retrieval benchmarking (Dense, BM25, Hybrid RRF, Hybrid+Reranker)
    - Document-scoped retrieval isolation verification
    - Answer groundedness & faithfulness scoring
    - Citation provenance & metadata completeness
    - Latency percentile calculation (P50, P90, P95, P99)
    - Token metrics auditing
    """

    def __init__(
        self,
        corpus: Optional[List[DocumentChunk]] = None,
        dataset_path: Optional[str] = None,
        llm: Optional[BaseLLM] = None
    ):
        self.corpus = corpus or get_evaluation_corpus()
        self.corpus_by_id = {c.chunk_id: c.content for c in self.corpus}
        self.dataset_path = dataset_path or os.path.join(
            os.path.dirname(__file__), "datasets", "rag_evaluation.json"
        )
        self.llm = llm or EvaluationMockLLM()
        self.dataset = self._load_dataset()
        self._init_retrievers()

    def _load_dataset(self) -> List[Dict[str, Any]]:
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _init_retrievers(self):
        """
        Builds the 4 distinct retrieval configurations over the evaluation corpus.
        """
        # Vector Store & Dense Retriever
        import tempfile
        embedder = HuggingFaceEmbedder()
        temp_dir = tempfile.mkdtemp(prefix="eval_faiss_")
        vstore = FAISSVectorStore(dimension=embedder.dimension, store_dir=temp_dir)
        embeddings = embedder.embed_documents([c.content for c in self.corpus])
        vstore.add_chunks(self.corpus, embeddings)
        self.dense_retriever = DenseRetriever(embedder=embedder, vector_store=vstore, min_relevance_threshold=0.0)

        # BM25 Keyword Retriever
        self.bm25_retriever = BM25KeywordRetriever()
        self.bm25_retriever.index_chunks(self.corpus)

        # Cross-Encoder Reranker
        self.reranker = CrossEncoderReranker()

        # Hybrid RRF (without reranker)
        self.hybrid_rrf = HybridRetriever(
            dense_retriever=self.dense_retriever,
            keyword_retriever=self.bm25_retriever,
            reranker=None,
            candidate_k=20
        )

        # Hybrid RRF + Cross-Encoder Reranker (Production Pipeline)
        self.hybrid_reranked = HybridRetriever(
            dense_retriever=self.dense_retriever,
            keyword_retriever=self.bm25_retriever,
            reranker=self.reranker,
            candidate_k=20
        )

        # Full RAG Engine with Production Hybrid + Reranker
        self.rag_engine = RAGEngine(
            retriever=self.hybrid_reranked,
            llm=self.llm,
            query_rewriter=ConversationalQueryRewriter(llm=self.llm),
            context_selector=ContextSelector(min_relevance_score=0.0, max_context_chunks=5)
        )

    def evaluate_retrieval_strategies(self) -> Dict[str, Dict[str, float]]:
        """
        Evaluates and compares the 4 retrieval strategies across all positive benchmark questions:
        1. Dense (FAISS)
        2. Keyword (BM25)
        3. Hybrid RRF
        4. Hybrid RRF + Reranker
        """
        strategies = {
            "Dense (FAISS)": self.dense_retriever,
            "Keyword (BM25)": self.bm25_retriever,
            "Hybrid RRF": self.hybrid_rrf,
            "Hybrid + Reranker": self.hybrid_reranked
        }

        results: Dict[str, Dict[str, float]] = {}

        # Filter questions with positive ground truth chunk IDs
        eval_cases = [q for q in self.dataset if q.get("relevant_chunk_ids")]

        for strat_name, retriever_obj in strategies.items():
            r1_list, r3_list, r5_list, r10_list, mrr_list = [], [], [], [], []

            for case in eval_cases:
                query = case["question"]
                gt_ids = case["relevant_chunk_ids"]
                filters = {}
                if case.get("document_ids"):
                    filters["document_ids"] = case["document_ids"]

                # Retrieve candidates
                if hasattr(retriever_obj, "retrieve"):
                    res = retriever_obj.retrieve(query=query, top_k=10, filters=filters)
                    retrieved_ids = [c.chunk_id for c, _ in res]
                elif hasattr(retriever_obj, "search"):
                    res = retriever_obj.search(query=query, top_k=10, filters=filters)
                    retrieved_ids = [c.chunk_id for c, _ in res]
                else:
                    retrieved_ids = []

                r1_list.append(calculate_recall_at_k(retrieved_ids, gt_ids, 1))
                r3_list.append(calculate_recall_at_k(retrieved_ids, gt_ids, 3))
                r5_list.append(calculate_recall_at_k(retrieved_ids, gt_ids, 5))
                r10_list.append(calculate_recall_at_k(retrieved_ids, gt_ids, 10))
                mrr_list.append(calculate_reciprocal_rank(retrieved_ids, gt_ids))

            n = len(eval_cases)
            results[strat_name] = {
                "Recall@1": round(sum(r1_list) / n, 4) if n > 0 else 0.0,
                "Recall@3": round(sum(r3_list) / n, 4) if n > 0 else 0.0,
                "Recall@5": round(sum(r5_list) / n, 4) if n > 0 else 0.0,
                "Recall@10": round(sum(r10_list) / n, 4) if n > 0 else 0.0,
                "MRR": calculate_mean_reciprocal_rank(mrr_list)
            }

        return results

    def evaluate_end_to_end_rag(self) -> Dict[str, Any]:
        """
        Executes end-to-end RAG pipeline across the full evaluation dataset.
        Measures retrieval, answer groundedness, citation accuracy,
        document-scoped isolation, refusal accuracy, latency percentiles, and token metrics.
        """
        retrieval_comparison = self.evaluate_retrieval_strategies()

        groundedness_scores: List[float] = []
        citation_scores: List[float] = []
        refusal_checks: List[float] = []
        scope_isolations: List[bool] = []
        total_latencies: List[float] = []
        stage_latencies: Dict[str, List[float]] = {
            "query_rewriting": [],
            "dense_retrieval": [],
            "bm25_retrieval": [],
            "rrf_fusion": [],
            "reranking": [],
            "context_selection": [],
            "llm_generation": [],
            "citation_validation": []
        }
        token_usage_total = 0
        token_calls = 0

        detailed_results: List[Dict[str, Any]] = []

        for case in self.dataset:
            history_objs = [ChatTurn(**h) for h in case.get("history", [])]
            doc_ids = case.get("document_ids")
            req = RAGQueryRequest(
                question=case["question"],
                workspace_id="eval-workspace",
                history=history_objs,
                document_ids=doc_ids,
                enable_query_rewriting=True,
                enable_reranking=True,
                top_k=5
            )

            resp: RAGQueryResponse = self.rag_engine.query(req)
            total_latencies.append(resp.latency_seconds * 1000.0)

            # Record trace stage latencies
            if resp.trace:
                stage_latencies["query_rewriting"].append(resp.trace.get("query_rewriting_latency_ms", 0.0))
                stage_latencies["dense_retrieval"].append(resp.trace.get("dense_retrieval_latency_ms", 0.0))
                stage_latencies["bm25_retrieval"].append(resp.trace.get("bm25_retrieval_latency_ms", 0.0))
                stage_latencies["rrf_fusion"].append(resp.trace.get("rrf_fusion_latency_ms", 0.0))
                stage_latencies["reranking"].append(resp.trace.get("reranking_latency_ms", 0.0))
                stage_latencies["context_selection"].append(resp.trace.get("context_selection_latency_ms", 0.0))
                stage_latencies["llm_generation"].append(resp.trace.get("llm_latency_ms", 0.0))
                stage_latencies["citation_validation"].append(resp.trace.get("citation_validation_latency_ms", 0.0))

            # Token metrics
            if resp.tokens and resp.tokens.get("total_tokens"):
                token_usage_total += resp.tokens["total_tokens"]
                token_calls += 1

            # 1. Document Scope Isolation check
            retrieved_chunk_ids = [c.chunk_id for c in resp.citations]
            retrieved_doc_ids = [c.document_id for c in resp.citations]
            scope_eval = evaluate_document_scope_isolation(retrieved_chunk_ids, retrieved_doc_ids, doc_ids)
            scope_isolations.append(scope_eval["is_isolated"])

            # 2. Citation Accuracy & Provenance
            cite_eval = evaluate_citation_quality(resp.citations, retrieved_chunk_ids, doc_ids)
            citation_scores.append(cite_eval["accuracy"])

            # 3. Groundedness Evaluation
            context_texts = [
                f"{c.source_title} {c.section_title or ''} {self.corpus_by_id.get(c.chunk_id, c.snippet)}"
                for c in resp.citations
            ]
            ground_eval = evaluate_groundedness(resp.answer, context_texts)
            groundedness_scores.append(ground_eval["score"])

            # 4. Refusal Accuracy
            expected_refusal = case.get("expected_refusal", False)
            actual_refusal = not resp.has_sufficient_context or ground_eval["is_refusal"]
            refusal_pass = (expected_refusal == actual_refusal)
            refusal_checks.append(1.0 if refusal_pass else 0.0)

            detailed_results.append({
                "id": case["id"],
                "question": case["question"],
                "category": case.get("category"),
                "expected_refusal": expected_refusal,
                "actual_refusal": actual_refusal,
                "refusal_pass": refusal_pass,
                "scope_isolated": scope_eval["is_isolated"],
                "citation_accuracy": cite_eval["accuracy"],
                "groundedness_score": ground_eval["score"],
                "citations_returned": len(resp.citations),
                "total_latency_ms": round(resp.latency_seconds * 1000.0, 2),
                "trace_id": resp.trace_id
            })

        total_questions = len(self.dataset)
        latency_summary = calculate_latency_percentiles(total_latencies)

        summary = {
            "total_questions": total_questions,
            "retrieval_comparison": retrieval_comparison,
            "answer_quality": {
                "groundedness_avg": round(sum(groundedness_scores) / total_questions, 4),
                "citation_accuracy_avg": round(sum(citation_scores) / total_questions, 4),
                "refusal_accuracy": round(sum(refusal_checks) / total_questions, 4),
                "document_scope_isolation_rate": round(sum(1.0 for s in scope_isolations if s) / total_questions, 4)
            },
            "latency_percentiles_ms": latency_summary,
            "average_stage_latencies_ms": {
                stage: round(sum(lats) / len(lats), 2) if lats else 0.0
                for stage, lats in stage_latencies.items()
            },
            "token_metrics": {
                "total_tokens_recorded": token_usage_total,
                "avg_tokens_per_query": round(token_usage_total / max(1, token_calls), 1) if token_calls > 0 else None,
                "model": getattr(self.llm, "model", "mock-eval-llm")
            },
            "detailed_results": detailed_results
        }

        return summary
