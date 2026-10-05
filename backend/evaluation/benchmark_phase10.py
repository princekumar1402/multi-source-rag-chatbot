import time
import json
import os
import sys
import copy
import statistics
import concurrent.futures
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.schemas.document import DocumentChunk, SourceType
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
from backend.app.services.llm.groq_provider import GroqLLM
from backend.app.core.config import settings
from backend.app.core.cache import cache_manager
from backend.evaluation.corpus import get_evaluation_corpus
from backend.evaluation.evaluator import EvaluationMockLLM

# Representative benchmark query dataset covering all 7 required archetypes
BENCHMARK_QUERIES: List[Dict[str, Any]] = [
    # 1. Simple factual queries
    {
        "id": "bench_01",
        "category": "simple_factual",
        "question": "What are the four Coffman conditions necessary for a deadlock in operating systems?",
        "document_ids": ["doc-pdf-eval-01"],
        "history": []
    },
    {
        "id": "bench_02",
        "category": "simple_factual",
        "question": "What are the ACID properties guaranteed in DBMS transaction management?",
        "document_ids": ["doc-docx-eval-02"],
        "history": []
    },
    {
        "id": "bench_03",
        "category": "simple_factual",
        "question": "What is the primary function of DNS in computer networking?",
        "document_ids": ["doc-txt-eval-03"],
        "history": []
    },
    # 2. Exact entity queries
    {
        "id": "bench_04",
        "category": "exact_entity",
        "question": "What is the job role and department of employee Rahul Sharma in the engineering staff list?",
        "document_ids": ["doc-csv-eval-05"],
        "history": []
    },
    {
        "id": "bench_05",
        "category": "exact_entity",
        "question": "What is the CGPA of Priya Patel in the student academic register?",
        "document_ids": ["doc-xlsx-eval-06"],
        "history": []
    },
    # 3. Structured data queries
    {
        "id": "bench_06",
        "category": "structured_data",
        "question": "Which employee has ID EMP-104 and what is their annual salary?",
        "document_ids": ["doc-csv-eval-05"],
        "history": []
    },
    {
        "id": "bench_07",
        "category": "structured_data",
        "question": "How many credits has student CS-2024-002 completed according to the academic report?",
        "document_ids": ["doc-xlsx-eval-06"],
        "history": []
    },
    # 4. Conversational queries (with history)
    {
        "id": "bench_08",
        "category": "conversational",
        "question": "What are its key advantages compared to HTTP/2?",
        "document_ids": ["doc-md-eval-04"],
        "history": [
            {"role": "user", "content": "What transport protocol does HTTP/3 rely on?"},
            {"role": "assistant", "content": "HTTP/3 relies on QUIC over UDP to eliminate head-of-line blocking."}
        ]
    },
    {
        "id": "bench_09",
        "category": "conversational",
        "question": "How does it handle preemption when the time slice expires?",
        "document_ids": ["doc-pdf-eval-01"],
        "history": [
            {"role": "user", "content": "Can you explain Round Robin CPU scheduling?"},
            {"role": "assistant", "content": "Round Robin assigns a fixed time quantum to each ready process."}
        ]
    },
    # 5. Document-scoped queries
    {
        "id": "bench_10",
        "category": "document_scoped",
        "question": "What loss function and backpropagation calculus was demonstrated in the video tutorial?",
        "document_ids": ["doc-yt-eval-08"],
        "history": []
    },
    {
        "id": "bench_11",
        "category": "document_scoped",
        "question": "What are the core consensus mechanisms used in proof-of-stake distributed ledgers?",
        "document_ids": ["doc-web-eval-07"],
        "history": []
    },
    # 6. Insufficient-context queries (expected refusal)
    {
        "id": "bench_12",
        "category": "insufficient_context",
        "question": "What was the quarterly stock dividend declared by Apple Inc in Q3 1999?",
        "document_ids": ["doc-pdf-eval-01"],
        "history": []
    },
    {
        "id": "bench_13",
        "category": "insufficient_context",
        "question": "What is the secret recipe for dark chocolate soufflé?",
        "document_ids": ["doc-csv-eval-05"],
        "history": []
    },
    # 7. Multi-hop queries
    {
        "id": "bench_14",
        "category": "multi_hop",
        "question": "Compare the head-of-line blocking behavior in HTTP/2 with the transport layer innovations introduced in HTTP/3 QUIC.",
        "document_ids": ["doc-md-eval-04", "doc-txt-eval-03"],
        "history": []
    },
    {
        "id": "bench_15",
        "category": "multi_hop",
        "question": "How does database multi-version concurrency control (MVCC) relate to transaction isolation levels during high write concurrency?",
        "document_ids": ["doc-docx-eval-02"],
        "history": []
    }
]

def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0, "mean": 0.0}
    s = sorted(values)
    n = len(s)

    def p(pct: float) -> float:
        k = (n - 1) * (pct / 100.0)
        f = int(k)
        c = min(f + 1, n - 1)
        return round(s[f] + (k - f) * (s[c] - s[f]), 2)

    return {
        "p50": p(50),
        "p75": p(75),
        "p90": p(90),
        "p95": p(95),
        "p99": p(99),
        "min": round(min(s), 2),
        "max": round(max(s), 2),
        "mean": round(statistics.mean(s), 2)
    }

class Phase10Benchmark:
    """
    Reproducible performance benchmarking harness for Phase 10:
    - Measures complete RAG request pipeline stages
    - Separate benchmarking for real provider (Groq) vs mock evaluation LLM
    - Granular percentiles (P50, P75, P90, P95, P99)
    - Stage-level profiling (Retrieval, Reranking, Database, LLM, Citations, Cache)
    - Concurrency load testing (1, 5, 10, 25 requests)
    - Cache hit/miss/eviction audit
    """

    def __init__(self, provider: str = "mock", model_name: Optional[str] = None):
        self.provider = provider.lower()
        self.corpus = get_evaluation_corpus()
        self._init_pipeline(model_name)

    def _init_pipeline(self, model_name: Optional[str]):
        # Setup Embedder
        self.embedder = HuggingFaceEmbedder()

        # Setup Vector Store with evaluation corpus
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="bench_faiss_")
        self.vector_store = FAISSVectorStore(dimension=self.embedder.dimension, store_dir=temp_dir)
        embeddings = self.embedder.embed_documents([c.content for c in self.corpus])
        self.vector_store.add_chunks(self.corpus, embeddings)

        # Setup BM25 Keyword Store
        self.bm25 = BM25KeywordRetriever()
        self.bm25.index_chunks(self.corpus)

        # Setup Reranker
        self.reranker = CrossEncoderReranker()

        # Hybrid Retriever
        self.retriever = HybridRetriever(
            dense_retriever=DenseRetriever(embedder=self.embedder, vector_store=self.vector_store, min_relevance_threshold=0.0),
            keyword_retriever=self.bm25,
            reranker=self.reranker,
            candidate_k=20
        )

        # Context Selector
        self.context_selector = ContextSelector(
            min_relevance_score=0.10,
            max_context_chunks=6,
            overlap_threshold=0.85
        )

        # Setup LLM based on provider
        if self.provider == "groq":
            target_model = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
            self.llm = GroqLLM(model=target_model)
            self.model_name = target_model
        else:
            self.llm = EvaluationMockLLM(model_name="eval-grounded-mock")
            self.model_name = "eval-grounded-mock"

        # RAG Engine
        self.engine = RAGEngine(
            retriever=self.retriever,
            llm=self.llm,
            query_rewriter=ConversationalQueryRewriter(llm=self.llm),
            context_selector=self.context_selector
        )

    def run_query(self, query_case: Dict[str, Any], workspace_id: str = "eval-workspace") -> Dict[str, Any]:
        history_objs = [ChatTurn(**h) for h in query_case.get("history", [])]
        req = RAGQueryRequest(
            question=query_case["question"],
            workspace_id=workspace_id,
            history=history_objs,
            document_ids=query_case.get("document_ids"),
            enable_query_rewriting=True,
            enable_reranking=True,
            top_k=5
        )

        t0 = time.perf_counter()
        resp: RAGQueryResponse = self.engine.query(req)
        wall_latency_ms = (time.perf_counter() - t0) * 1000

        trace = resp.trace or {}
        tokens = resp.tokens or {}

        return {
            "id": query_case["id"],
            "category": query_case["category"],
            "wall_latency_ms": round(wall_latency_ms, 2),
            "trace_total_ms": trace.get("total_latency_ms", round(wall_latency_ms, 2)),
            "query_rewrite_ms": trace.get("query_rewriting_latency_ms", 0.0),
            "cache_lookup_ms": trace.get("cache_lookup_latency_ms", 0.0),
            "metadata_filter_ms": trace.get("metadata_filtering_latency_ms", 0.0),
            "dense_retrieval_ms": trace.get("dense_retrieval_latency_ms", 0.0),
            "bm25_retrieval_ms": trace.get("bm25_retrieval_latency_ms", 0.0),
            "rrf_fusion_ms": trace.get("rrf_fusion_latency_ms", 0.0),
            "reranking_ms": trace.get("reranking_latency_ms", 0.0),
            "context_selection_ms": trace.get("context_selection_latency_ms", 0.0),
            "prompt_construction_ms": trace.get("prompt_construction_latency_ms", 0.0),
            "llm_generation_ms": trace.get("llm_latency_ms", 0.0),
            "citation_validation_ms": trace.get("citation_validation_latency_ms", 0.0),
            "cache_hit": trace.get("cache_hit", False),
            "cache_stage": trace.get("cache_stage", "none"),
            "citations_count": len(resp.citations),
            "has_sufficient_context": resp.has_sufficient_context,
            "input_tokens": tokens.get("input_tokens"),
            "output_tokens": tokens.get("output_tokens"),
            "total_tokens": tokens.get("total_tokens")
        }

    def execute_benchmark(self, repetitions: int = 1, clear_cache_first: bool = True) -> Dict[str, Any]:
        """Runs the benchmark suite across all queries."""
        if clear_cache_first:
            cache_manager.clear_all()

        results: List[Dict[str, Any]] = []
        for rep in range(repetitions):
            for case in BENCHMARK_QUERIES:
                res = self.run_query(case)
                results.append(res)

        # Aggregate metrics
        total_latencies = [r["wall_latency_ms"] for r in results]
        rewrite_latencies = [r["query_rewrite_ms"] for r in results]
        cache_lookup_latencies = [r["cache_lookup_ms"] for r in results]
        dense_latencies = [r["dense_retrieval_ms"] for r in results]
        bm25_latencies = [r["bm25_retrieval_ms"] for r in results]
        rrf_latencies = [r["rrf_fusion_ms"] for r in results]
        rerank_latencies = [r["reranking_ms"] for r in results]
        context_latencies = [r["context_selection_ms"] for r in results]
        llm_latencies = [r["llm_generation_ms"] for r in results]
        citation_latencies = [r["citation_validation_ms"] for r in results]

        cache_hits = sum(1 for r in results if r["cache_hit"])
        cache_hit_rate = round((cache_hits / len(results)) * 100.0, 2) if results else 0.0

        all_input_tokens = [r["input_tokens"] for r in results if r["input_tokens"] is not None]
        all_output_tokens = [r["output_tokens"] for r in results if r["output_tokens"] is not None]
        all_total_tokens = [r["total_tokens"] for r in results if r["total_tokens"] is not None]

        summary = {
            "benchmark": "phase10",
            "provider": self.provider,
            "model": self.model_name,
            "queries_executed": len(results),
            "unique_queries": len(BENCHMARK_QUERIES),
            "repetitions": repetitions,
            "latency_ms": calculate_percentiles(total_latencies),
            "stages": {
                "query_rewrite": calculate_percentiles(rewrite_latencies),
                "cache_lookup": calculate_percentiles(cache_lookup_latencies),
                "dense_faiss": calculate_percentiles(dense_latencies),
                "bm25": calculate_percentiles(bm25_latencies),
                "rrf_fusion": calculate_percentiles(rrf_latencies),
                "reranker": calculate_percentiles(rerank_latencies),
                "context_selection": calculate_percentiles(context_latencies),
                "llm_generation": calculate_percentiles(llm_latencies),
                "citation_validation": calculate_percentiles(citation_latencies)
            },
            "cache": {
                "hits": cache_hits,
                "misses": len(results) - cache_hits,
                "hit_rate_pct": cache_hit_rate,
                "stats": cache_manager.get_all_stats()
            },
            "tokens": {
                "total_recorded": sum(all_total_tokens),
                "avg_input_tokens": round(statistics.mean(all_input_tokens), 1) if all_input_tokens else 0,
                "avg_output_tokens": round(statistics.mean(all_output_tokens), 1) if all_output_tokens else 0,
                "avg_total_tokens": round(statistics.mean(all_total_tokens), 1) if all_total_tokens else 0
            }
        }
        return summary

    def run_concurrency_test(self, concurrency_levels: List[int] = [1, 5, 10, 25]) -> Dict[str, Any]:
        """
        Runs concurrency tests across multiple simultaneous threads:
        Measures throughput (req/sec), latency percentiles, error rate, cache contention.
        """
        concurrency_results = {}
        sample_queries = BENCHMARK_QUERIES[:8]  # Representative batch of 8 queries

        for c in concurrency_levels:
            total_requests = max(c * 2, len(sample_queries))
            req_list = [sample_queries[i % len(sample_queries)] for i in range(total_requests)]

            t_start = time.perf_counter()
            latencies = []
            errors = 0

            with concurrent.futures.ThreadPoolExecutor(max_workers=c) as executor:
                futures = [executor.submit(self.run_query, q, "eval-workspace") for i, q in enumerate(req_list)]
                for f in concurrent.futures.as_completed(futures):
                    try:
                        res = f.result()
                        latencies.append(res["wall_latency_ms"])
                    except Exception as e:
                        errors += 1

            total_time_s = time.perf_counter() - t_start
            throughput = round(total_requests / total_time_s, 2) if total_time_s > 0 else 0.0

            concurrency_results[f"concurrency_{c}"] = {
                "concurrency": c,
                "total_requests": total_requests,
                "duration_seconds": round(total_time_s, 3),
                "throughput_req_per_sec": throughput,
                "error_rate_pct": round((errors / total_requests) * 100.0, 2),
                "latency_ms": calculate_percentiles(latencies)
            }

        return concurrency_results

def run_full_phase10_benchmark() -> Dict[str, Any]:
    print("=" * 60)
    print("STARTING PHASE 10 COMPREHENSIVE RUNTIME BENCHMARK")
    print("=" * 60)

    # 1. Deterministic Mock Benchmark (Baseline vs Cached)
    print("\n[1/3] Running Deterministic Benchmark (Mock LLM)...")
    mock_bench = Phase10Benchmark(provider="mock")
    # Baseline: Cold Cache
    print("  -> Running Cold Cache Baseline (Mock)...")
    baseline_mock = mock_bench.execute_benchmark(repetitions=1, clear_cache_first=True)
    # Optimized: Warm Cache (2nd pass)
    print("  -> Running Warm Cache Optimized (Mock)...")
    optimized_mock = mock_bench.execute_benchmark(repetitions=2, clear_cache_first=False)

    # Concurrency test on Mock
    print("  -> Running Concurrency Load Test (1, 5, 10, 25 threads)...")
    concurrency_mock = mock_bench.run_concurrency_test([1, 5, 10, 25])

    # 2. Real Groq Provider Benchmark
    real_results = None
    groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if groq_api_key and groq_api_key.startswith("gsk_"):
        print("\n[2/3] Running Real Groq Provider Benchmark (Live API)...")
        try:
            groq_bench = Phase10Benchmark(provider="groq")
            print("  -> Running Cold Cache Baseline (Groq)...")
            groq_baseline = groq_bench.execute_benchmark(repetitions=1, clear_cache_first=True)
            print("  -> Running Warm Cache Optimized (Groq)...")
            groq_optimized = groq_bench.execute_benchmark(repetitions=1, clear_cache_first=False)
            real_results = {
                "groq_baseline": groq_baseline,
                "groq_optimized": groq_optimized
            }
        except Exception as e:
            print(f"  [WARNING] Real Groq benchmark failed ({e}). Proceeding with mock results.")
            real_results = {"error": str(e)}
    else:
        print("\n[2/3] Skipping Live Groq Benchmark (GROQ_API_KEY not configured or invalid).")

    full_output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "mock_evaluation": {
            "baseline": baseline_mock,
            "optimized": optimized_mock,
            "concurrency": concurrency_mock
        },
        "real_provider": real_results
    }

    # Save to disk
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_file = os.path.join(workspace_root, "backend", "evaluation", "phase10_benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(full_output, f, indent=2)
    print(f"\n[3/3] Benchmark complete! Results saved to: {out_file}")
    print("=" * 60)
    return full_output

if __name__ == "__main__":
    run_full_phase10_benchmark()
