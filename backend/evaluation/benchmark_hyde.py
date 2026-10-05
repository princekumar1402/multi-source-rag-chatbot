import time
import json
from typing import List, Dict, Any

from backend.evaluation.evaluator import RAGEvaluator
from backend.evaluation.metrics import (
    calculate_recall_at_k,
    calculate_reciprocal_rank,
    calculate_mean_reciprocal_rank
)
from backend.app.services.rag.hyde import HyDERetriever

def run_hyde_experiment():
    print("=" * 60)
    print("RUNNING HYDE (HYPOTHETICAL DOCUMENT EMBEDDINGS) EXPERIMENT")
    print("=" * 60)

    evaluator = RAGEvaluator()
    eval_cases = [q for q in evaluator.dataset if q.get("relevant_chunk_ids")]

    # 1. Normal Dense Retrieval
    t0 = time.perf_counter()
    r1_norm, r5_norm, mrr_norm = [], [], []
    for case in eval_cases:
        query = case["question"]
        gt_ids = case["relevant_chunk_ids"]
        filters = {"document_ids": case["document_ids"]} if case.get("document_ids") else {}
        res = evaluator.dense_retriever.retrieve(query=query, top_k=10, filters=filters)
        ret_ids = [c.chunk_id for c, _ in res]
        r1_norm.append(calculate_recall_at_k(ret_ids, gt_ids, 1))
        r5_norm.append(calculate_recall_at_k(ret_ids, gt_ids, 5))
        mrr_norm.append(calculate_reciprocal_rank(ret_ids, gt_ids))
    t_norm = (time.perf_counter() - t0) * 1000

    # 2. HyDE Dense Retrieval
    hyde_retriever = HyDERetriever(base_retriever=evaluator.dense_retriever, llm=evaluator.llm)
    t0 = time.perf_counter()
    r1_hyde, r5_hyde, mrr_hyde = [], [], []
    for case in eval_cases:
        query = case["question"]
        gt_ids = case["relevant_chunk_ids"]
        filters = {"document_ids": case["document_ids"]} if case.get("document_ids") else {}
        res = hyde_retriever.retrieve(query=query, top_k=10, filters=filters)
        ret_ids = [c.chunk_id for c, _ in res]
        r1_hyde.append(calculate_recall_at_k(ret_ids, gt_ids, 1))
        r5_hyde.append(calculate_recall_at_k(ret_ids, gt_ids, 5))
        mrr_hyde.append(calculate_reciprocal_rank(ret_ids, gt_ids))
    t_hyde = (time.perf_counter() - t0) * 1000

    n = len(eval_cases)
    results = {
        "normal_dense": {
            "Recall@1": round(sum(r1_norm) / n, 4),
            "Recall@5": round(sum(r5_norm) / n, 4),
            "MRR": calculate_mean_reciprocal_rank(mrr_norm),
            "total_latency_ms": round(t_norm, 2),
            "avg_latency_ms": round(t_norm / n, 2),
            "llm_calls_per_query": 0
        },
        "hyde_dense": {
            "Recall@1": round(sum(r1_hyde) / n, 4),
            "Recall@5": round(sum(r5_hyde) / n, 4),
            "MRR": calculate_mean_reciprocal_rank(mrr_hyde),
            "total_latency_ms": round(t_hyde, 2),
            "avg_latency_ms": round(t_hyde / n, 2),
            "llm_calls_per_query": 1
        }
    }

    print("\nHYDE EXPERIMENT RESULTS:")
    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    run_hyde_experiment()
