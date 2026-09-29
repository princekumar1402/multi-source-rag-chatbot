import json
import os
import time
import tempfile
import shutil
from typing import Dict, Any, List

from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.services.rag.bm25 import BM25Retriever
from backend.app.services.rag.reranker import CrossEncoderReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.tests.evaluation.corpus import get_evaluation_corpus

def evaluate_retriever(
    name: str,
    retriever: Any,
    eval_cases: List[Dict[str, Any]],
    top_k: int = 5
) -> Dict[str, Any]:
    positive_cases = [c for c in eval_cases if c["source_type"] != "unknown"]
    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    metadata_matches = 0
    latencies_ms = []
    details = []

    for case in positive_cases:
        q = case["question"]
        t0 = time.perf_counter()
        retrieved = retriever.retrieve(q, top_k=top_k, filters={"workspace_id": "eval-workspace"})
        latency = (time.perf_counter() - t0) * 1000
        latencies_ms.append(latency)

        retrieved_chunks = [chunk for chunk, score in retrieved]
        expected_src = case["expected_source"]
        is_hit_1 = False
        is_hit_3 = False
        is_hit_5 = False

        for rank, chunk in enumerate(retrieved_chunks):
            match = (chunk.metadata.source_name == expected_src or
                     chunk.metadata.source_url == expected_src or
                     chunk.metadata.file_name == expected_src)
            if match:
                if rank == 0:
                    is_hit_1 = True
                if rank < 3:
                    is_hit_3 = True
                if rank < 5:
                    is_hit_5 = True

                # Check metadata preservation
                meta_ok = True
                for k, v in case.get("expected_metadata", {}).items():
                    if getattr(chunk.metadata, k, None) != v:
                        meta_ok = False
                        break
                if meta_ok:
                    metadata_matches += 1
                break

        if is_hit_1: hits_at_1 += 1
        if is_hit_3: hits_at_3 += 1
        if is_hit_5: hits_at_5 += 1

        details.append({
            "id": case["id"],
            "question": q,
            "hit@1": is_hit_1,
            "hit@3": is_hit_3,
            "hit@5": is_hit_5,
            "latency_ms": round(latency, 2),
            "top_retrieved": [(c.metadata.source_name, round(s, 4)) for c, s in retrieved]
        })

    total_pos = len(positive_cases)
    summary = {
        "mode": name,
        "total_cases": total_pos,
        "recall@1": round(hits_at_1 / total_pos, 4) if total_pos else 0.0,
        "recall@3": round(hits_at_3 / total_pos, 4) if total_pos else 0.0,
        "recall@5": round(hits_at_5 / total_pos, 4) if total_pos else 0.0,
        "metadata_accuracy": round(metadata_matches / total_pos, 4) if total_pos else 0.0,
        "avg_latency_ms": round(sum(latencies_ms) / len(latencies_ms), 2) if latencies_ms else 0.0,
        "details": details
    }
    return summary

def run_comprehensive_evaluation() -> Dict[str, Any]:
    dataset_path = os.path.join(os.path.dirname(__file__), "rag_eval_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    temp_dir = tempfile.mkdtemp()
    try:
        embedder = HuggingFaceEmbedder()
        vector_store = FAISSVectorStore(dimension=embedder.dimension, store_dir=temp_dir)

        # Index corpus in both FAISS and BM25
        corpus = get_evaluation_corpus()
        texts = [chunk.content for chunk in corpus]
        vectors = embedder.embed_documents(texts)
        vector_store.add_chunks(corpus, vectors)

        bm25_retriever = BM25Retriever()
        bm25_retriever.index_chunks(corpus)

        reranker = CrossEncoderReranker(enabled=True)

        # 1. Baseline Dense Retriever
        dense_retriever = DenseRetrieverWithReranker(
            embedder=embedder,
            vector_store=vector_store,
            min_relevance_threshold=0.0
        )
        dense_metrics = evaluate_retriever("Dense_Baseline", dense_retriever, eval_cases)

        # 2. Pure BM25 Keyword Retriever
        class BM25Adapter:
            def __init__(self, bm25):
                self.bm25 = bm25
            def retrieve(self, q, top_k=5, filters=None):
                return self.bm25.search(q, top_k=top_k, filters=filters)

        bm25_metrics = evaluate_retriever("BM25_Only", BM25Adapter(bm25_retriever), eval_cases)

        # 3. Hybrid Retriever (Dense + BM25 with RRF)
        hybrid_no_reranker = HybridRetriever(
            dense_retriever=dense_retriever,
            keyword_retriever=bm25_retriever,
            reranker=None,
            candidate_k=20,
            rrf_k=60
        )
        hybrid_metrics = evaluate_retriever("Hybrid_RRF", hybrid_no_reranker, eval_cases)

        # 4. Hybrid Retriever + Cross-Encoder Reranker
        hybrid_with_reranker = HybridRetriever(
            dense_retriever=dense_retriever,
            keyword_retriever=bm25_retriever,
            reranker=reranker,
            candidate_k=20,
            rrf_k=60
        )
        hybrid_rerank_metrics = evaluate_retriever("Hybrid_RRF_Reranker", hybrid_with_reranker, eval_cases)

        comparison = {
            "Dense_Baseline": dense_metrics,
            "BM25_Only": bm25_metrics,
            "Hybrid_RRF": hybrid_metrics,
            "Hybrid_RRF_Reranker": hybrid_rerank_metrics
        }

        print("\n======================= RAG RETRIEVAL EVALUATION RESULTS =======================")
        print(f"{'Configuration':<22} | {'Recall@1':<10} | {'Recall@3':<10} | {'Recall@5':<10} | {'Metadata Acc':<12} | {'Avg Latency':<12}")
        print("-" * 88)
        for name, m in comparison.items():
            print(f"{name:<22} | {m['recall@1']*100:>7.1f}%   | {m['recall@3']*100:>7.1f}%   | {m['recall@5']*100:>7.1f}%   | {m['metadata_accuracy']*100:>10.1f}% | {m['avg_latency_ms']:>8.2f} ms")
        print("================================================================================\n")

        out_path = os.path.join(os.path.dirname(__file__), "evaluation_comparison.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2)

        return comparison
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_comprehensive_evaluation()
