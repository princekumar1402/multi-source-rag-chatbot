import time
from typing import List, Tuple, Dict, Any, Optional
from backend.app.schemas.document import DocumentChunk
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.services.rag.bm25 import BaseKeywordRetriever
from backend.app.services.rag.reranker import BaseReranker
from backend.app.core.config import settings
from backend.app.core.logging import logger

class HybridRetriever(BaseRetriever):
    """
    Production Hybrid Retriever combining Dense Vector and BM25 Lexical Search.
    Fuses candidate rankings via Reciprocal Rank Fusion (RRF) and rescores via Cross-Encoder Reranker.
    """

    def __init__(
        self,
        dense_retriever: BaseRetriever,
        keyword_retriever: BaseKeywordRetriever,
        reranker: Optional[BaseReranker] = None,
        dense_weight: float = 0.5,
        bm25_weight: float = 0.5,
        candidate_k: int = 20,
        rrf_k: int = 60
    ):
        self.dense_retriever = dense_retriever
        self.keyword_retriever = keyword_retriever
        self.reranker = reranker
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        self.candidate_k = candidate_k
        self.rrf_k = rrf_k

    def _reciprocal_rank_fusion(
        self,
        dense_results: List[Tuple[DocumentChunk, float]],
        bm25_results: List[Tuple[DocumentChunk, float]]
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Reciprocal Rank Fusion (RRF):
        RRF_Score(d) = w_dense * (1 / (k + rank_dense)) + w_bm25 * (1 / (k + rank_bm25))
        """
        chunk_map: Dict[str, DocumentChunk] = {}
        rrf_scores: Dict[str, float] = {}

        # Dense rank contributions
        for rank, (chunk, _) in enumerate(dense_results, start=1):
            chunk_map[chunk.chunk_id] = chunk
            dense_rrf = self.dense_weight / (self.rrf_k + rank)
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + dense_rrf

        # BM25 rank contributions
        for rank, (chunk, _) in enumerate(bm25_results, start=1):
            chunk_map[chunk.chunk_id] = chunk
            bm25_rrf = self.bm25_weight / (self.rrf_k + rank)
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + bm25_rrf

        if not rrf_scores:
            return []

        # Sort descending by RRF score
        sorted_chunks = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        max_rrf = sorted_chunks[0][1] if sorted_chunks else 1.0

        # Scale normalized scores to [0.0, 1.0]
        fused: List[Tuple[DocumentChunk, float]] = []
        for cid, score in sorted_chunks:
            normalized = score / max_rrf if max_rrf > 0 else 0.0
            fused.append((chunk_map[cid], round(normalized, 4)))

        return fused

    def retrieve_with_details(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes hybrid retrieval and returns complete debug details:
        dense_candidates, bm25_candidates, fused_candidates, reranked_candidates, latencies.
        """
        t0 = time.perf_counter()
        dense_results: List[Tuple[DocumentChunk, float]] = []
        bm25_results: List[Tuple[DocumentChunk, float]] = []

        # 1. Dense retrieval with fallback
        t_dense_start = time.perf_counter()
        try:
            dense_results = self.dense_retriever.retrieve(
                query=query,
                top_k=self.candidate_k,
                filters=filters
            )
        except Exception as e:
            logger.warning(f"Dense retrieval failed: {e}. Relying on BM25.")
        t_dense_ms = (time.perf_counter() - t_dense_start) * 1000

        # 2. BM25 keyword retrieval with fallback
        t_bm25_start = time.perf_counter()
        try:
            bm25_results = self.keyword_retriever.search(
                query=query,
                top_k=self.candidate_k,
                filters=filters
            )
        except Exception as e:
            logger.warning(f"BM25 retrieval failed: {e}. Relying on Dense.")
        t_bm25_ms = (time.perf_counter() - t_bm25_start) * 1000

        t_retrieval = (time.perf_counter() - t0) * 1000

        # 3. Candidate Fusion
        t1 = time.perf_counter()
        if dense_results and bm25_results:
            fused_candidates = self._reciprocal_rank_fusion(dense_results, bm25_results)
        elif dense_results:
            logger.info("Hybrid falling back to Dense-only candidates")
            fused_candidates = dense_results
        elif bm25_results:
            logger.info("Hybrid falling back to BM25-only candidates")
            fused_candidates = bm25_results
        else:
            logger.info("No candidates returned from either dense or BM25 retrieval.")
            fused_candidates = []

        t_fusion = (time.perf_counter() - t1) * 1000

        # 4. Cross-Encoder Reranking
        t2 = time.perf_counter()
        reranked_candidates = fused_candidates
        if self.reranker and fused_candidates:
            try:
                reranked_candidates = self.reranker.rerank(
                    query=query,
                    candidates=fused_candidates[:self.candidate_k],
                    top_k=top_k * 2
                )
            except Exception as e:
                logger.warning(f"Reranking failed: {e}. Using fused candidates.")
                reranked_candidates = fused_candidates[:top_k * 2]

        t_rerank = (time.perf_counter() - t2) * 1000

        final_chunks = reranked_candidates[:top_k]

        return {
            "results": final_chunks,
            "dense_candidates": dense_results,
            "bm25_candidates": bm25_results,
            "fused_candidates": fused_candidates,
            "reranked_candidates": reranked_candidates,
            "dense_ms": round(t_dense_ms, 2),
            "bm25_ms": round(t_bm25_ms, 2),
            "retrieval_ms": round(t_retrieval, 2),
            "fusion_ms": round(t_fusion, 2),
            "rerank_ms": round(t_rerank, 2)
        }

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        details = self.retrieve_with_details(query=query, top_k=top_k, filters=filters)
        return details["results"]
