import json
import os
import time
import tempfile
import shutil
from typing import Dict, Any, List

from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.tests.evaluation.corpus import get_evaluation_corpus

def run_baseline_evaluation() -> Dict[str, Any]:
    dataset_path = os.path.join(os.path.dirname(__file__), "rag_eval_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        eval_cases = json.load(f)

    # Temporary directory for isolated vector store
    temp_dir = tempfile.mkdtemp()
    try:
        embedder = HuggingFaceEmbedder()
        vector_store = FAISSVectorStore(dimension=embedder.dimension, store_dir=temp_dir)

        # Index evaluation corpus
        corpus = get_evaluation_corpus()
        texts = [chunk.content for chunk in corpus]
        vectors = embedder.embed_documents(texts)
        vector_store.add_chunks(corpus, vectors)

        retriever = DenseRetrieverWithReranker(
            embedder=embedder,
            vector_store=vector_store,
            min_relevance_threshold=0.1
        )

        results = []
        positive_cases = [c for c in eval_cases if c["source_type"] != "unknown"]
        negative_cases = [c for c in eval_cases if c["source_type"] == "unknown"]

        hits_at_1 = 0
        hits_at_3 = 0
        hits_at_5 = 0
        metadata_matches = 0
        latencies_ms = []

        for case in positive_cases:
            q = case["question"]
            t0 = time.perf_counter()
            retrieved = retriever.retrieve(q, top_k=5, filters={"workspace_id": "eval-workspace"})
            latency = (time.perf_counter() - t0) * 1000
            latencies_ms.append(latency)

            retrieved_chunks = [chunk for chunk, score in retrieved]
            top_sources = [c.metadata.source_name for c in retrieved_chunks]
            top_urls = [c.metadata.source_url for c in retrieved_chunks]

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
                    
                    # Verify metadata integrity
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

            results.append({
                "id": case["id"],
                "question": q,
                "hit@1": is_hit_1,
                "hit@3": is_hit_3,
                "hit@5": is_hit_5,
                "latency_ms": round(latency, 2),
                "top_retrieved": [(c.metadata.source_name, round(s, 4)) for c, s in retrieved]
            })

        total_pos = len(positive_cases)
        recall_at_1 = hits_at_1 / total_pos if total_pos else 0.0
        recall_at_3 = hits_at_3 / total_pos if total_pos else 0.0
        recall_at_5 = hits_at_5 / total_pos if total_pos else 0.0
        metadata_acc = metadata_matches / total_pos if total_pos else 0.0
        avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0

        summary = {
            "mode": "baseline_dense",
            "total_positive_cases": total_pos,
            "recall@1": round(recall_at_1, 4),
            "recall@3": round(recall_at_3, 4),
            "recall@5": round(recall_at_5, 4),
            "metadata_accuracy": round(metadata_acc, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "details": results
        }

        print("=== BASELINE DENSE RETRIEVAL METRICS ===")
        print(f"Recall@1: {summary['recall@1'] * 100:.1f}%")
        print(f"Recall@3: {summary['recall@3'] * 100:.1f}%")
        print(f"Recall@5: {summary['recall@5'] * 100:.1f}%")
        print(f"Metadata Preservation: {summary['metadata_accuracy'] * 100:.1f}%")
        print(f"Average Latency: {summary['avg_latency_ms']} ms")

        # Save baseline results to file
        out_path = os.path.join(os.path.dirname(__file__), "baseline_results.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_baseline_evaluation()
