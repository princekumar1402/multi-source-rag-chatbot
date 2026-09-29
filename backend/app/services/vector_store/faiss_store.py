import os
import pickle
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import faiss

from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.schemas.document import DocumentChunk
from backend.app.core.config import settings
from backend.app.core.logging import logger

class FAISSVectorStore(BaseVectorStore):
    """
    Persistent FAISS implementation of BaseVectorStore.
    Uses Inner Product (cosine similarity on normalized vectors) with disk serialization.
    """

    def __init__(self, dimension: int, store_dir: Optional[str] = None):
        self.dimension = dimension
        self.store_dir = store_dir or settings.VECTOR_STORE_PATH
        self.index_path = os.path.join(self.store_dir, "faiss_index.bin")
        self.meta_path = os.path.join(self.store_dir, "faiss_chunks.pkl")
        
        self.index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.dimension)
        self.chunks: List[DocumentChunk] = []
        
        os.makedirs(self.store_dir, exist_ok=True)
        self.load()

    def add_chunks(
        self,
        chunks: List[DocumentChunk],
        embeddings: List[List[float]]
    ) -> List[str]:
        if not chunks or not embeddings:
            return []

        vectors_np = np.array(embeddings, dtype=np.float32)
        # Normalize for cosine similarity
        faiss.normalize_L2(vectors_np)

        self.index.add(vectors_np)
        self.chunks.extend(chunks)
        self.persist()

        logger.info(f"Added {len(chunks)} chunks to FAISS store. Total count: {self.index.ntotal}")
        return [chunk.chunk_id for chunk in chunks]

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        if self.index.ntotal == 0:
            return []

        q_vec = np.array([query_vector], dtype=np.float32)
        faiss.normalize_L2(q_vec)

        # Retrieve a candidate pool larger than top_k to accommodate metadata filtering
        fetch_k = min(self.index.ntotal, max(top_k * 4, 20))
        scores, indices = self.index.search(q_vec, fetch_k)

        results: List[Tuple[DocumentChunk, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]

            # Apply metadata filters if provided
            if filters:
                match = True
                for k, v in filters.items():
                    if k == "workspace_id" and chunk.metadata.workspace_id != v:
                        match = False
                        break
                    elif k == "document_ids" and v and chunk.metadata.document_id not in v:
                        match = False
                        break
                    elif k == "source_type" and chunk.metadata.source_type != v:
                        match = False
                        break
                if not match:
                    continue

            results.append((chunk, float(score)))
            if len(results) >= top_k:
                break

        return results

    def delete_document(self, document_id: str) -> bool:
        """
        Removes all chunks for document_id and rebuilds the FAISS index.
        """
        initial_count = len(self.chunks)
        retained = [(i, c) for i, c in enumerate(self.chunks) if c.metadata.document_id != document_id]
        
        if len(retained) == initial_count:
            return False

        # Rebuild index with retained chunks
        new_index = faiss.IndexFlatIP(self.dimension)
        if retained:
            retained_indices = [i for i, _ in retained]
            # Extract retained vectors from existing index
            vectors = np.zeros((len(retained), self.dimension), dtype=np.float32)
            for new_i, old_i in enumerate(retained_indices):
                vectors[new_i] = self.index.reconstruct(old_i)
            new_index.add(vectors)

        self.index = new_index
        self.chunks = [c for _, c in retained]
        self.persist()
        logger.info(f"Deleted document {document_id}. Chunks reduced from {initial_count} to {len(self.chunks)}")
        return True

    def persist(self) -> None:
        try:
            faiss.write_index(self.index, self.index_path)
            with open(self.meta_path, "wb") as f:
                pickle.dump(self.chunks, f)
            logger.debug(f"Persisted FAISS index with {self.index.ntotal} vectors to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to persist FAISS index: {e}")

    def load(self) -> None:
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.meta_path, "rb") as f:
                    self.chunks = pickle.load(f)
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors from {self.index_path}")
            except Exception as e:
                logger.warning(f"Could not load existing FAISS index: {e}. Initializing fresh index.")
                self.index = faiss.IndexFlatIP(self.dimension)
                self.chunks = []

    def count(self, workspace_id: Optional[str] = None) -> int:
        if not workspace_id:
            return len(self.chunks)
        return sum(1 for c in self.chunks if c.metadata.workspace_id == workspace_id)

    def get_all_chunks(self, filters: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        """Retrieve all document chunks, optionally filtered."""
        if not filters:
            return list(self.chunks)

        results = []
        for chunk in self.chunks:
            match = True
            for k, v in filters.items():
                if k == "workspace_id" and chunk.metadata.workspace_id != v:
                    match = False
                    break
                elif k == "document_ids" and v and chunk.metadata.document_id not in v:
                    match = False
                    break
                elif k == "document_id" and chunk.metadata.document_id != v:
                    match = False
                    break
                elif k == "source_type" and chunk.metadata.source_type != v:
                    match = False
                    break
            if match:
                results.append(chunk)
        return results
