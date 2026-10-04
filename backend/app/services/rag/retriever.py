from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from backend.app.schemas.document import DocumentChunk
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.core.logging import logger

class BaseRetriever(ABC):
    """
    Abstract interface for multi-source knowledge retrieval.
    Designed to support dense vector, BM25, hybrid search, and cross-encoder reranking.
    """

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """Retrieve relevant document chunks with relevance scores."""
        pass

class DenseRetrieverWithReranker(BaseRetriever):
    """
    Production-grade dense retriever with metadata filtering and relevance scoring.
    Ready for future hybrid expansion (BM25 + Dense RRF fusion).
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        min_relevance_threshold: float = 0.25
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.min_relevance_threshold = min_relevance_threshold

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        logger.info(f"Retrieving top {top_k} chunks for query: '{query}' with filters: {filters}")

        # 1. Dense embedding of query
        query_vector = self.embedder.embed_query(query)

        # 2. Vector search with metadata filters
        candidates = self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k * 2, # Fetch wider candidate pool for score filtering
            filters=filters
        )

        if not candidates:
            logger.info("No candidates returned from vector store.")
            return []

        # 3. Relevance filtering / Reranking
        filtered_results: List[Tuple[DocumentChunk, float]] = []
        for chunk, score in candidates:
            # Cosine similarity score filtering
            if score >= self.min_relevance_threshold:
                filtered_results.append((chunk, score))

        # Sort descending by score and slice to top_k
        filtered_results.sort(key=lambda x: x[1], reverse=True)
        final_chunks = filtered_results[:top_k]

        logger.info(f"Retrieved {len(final_chunks)} chunks above threshold {self.min_relevance_threshold}")
        return final_chunks

# Canonical alias
DenseRetriever = DenseRetrieverWithReranker

