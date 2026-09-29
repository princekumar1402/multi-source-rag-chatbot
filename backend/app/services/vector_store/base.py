from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from backend.app.schemas.document import DocumentChunk

class BaseVectorStore(ABC):
    """
    Abstract interface isolating Vector Database operations.
    Enables swapping FAISS for Qdrant, PGVector, or Pinecone without altering RAG logic.
    """

    @abstractmethod
    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]]
    ) -> List[str]:
        """
        Store chunks and their corresponding embedding vectors.
        Returns list of stored vector IDs.
        """
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for top-k nearest chunks with metadata filtering.
        Returns list of (DocumentChunk, score) tuples.
        """
        pass

    @abstractmethod
    def delete_document(self, document_id: str) -> bool:
        """Remove all chunks associated with a document_id."""
        pass

    @abstractmethod
    def persist(self) -> None:
        """Save vector index and chunk store to persistent disk storage."""
        pass

    @abstractmethod
    def count(self, workspace_id: Optional[str] = None) -> int:
        """Count total vectors indexed."""
        pass

    @abstractmethod
    def get_all_chunks(self, filters: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        """Retrieve all document chunks matching filters."""
        pass
