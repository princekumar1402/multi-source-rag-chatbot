import math
import re
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional, Set
from collections import Counter

from backend.app.schemas.document import DocumentChunk
from backend.app.core.logging import logger

class BaseKeywordRetriever(ABC):
    """
    Abstract interface for keyword / lexical document retrieval.
    """

    @abstractmethod
    def index_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Add or update chunks in the keyword index."""
        pass

    @abstractmethod
    def remove_document(self, document_id: str) -> None:
        """Remove all chunks associated with a document_id."""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Execute keyword search with metadata filtering.
        Returns list of (DocumentChunk, relevance_score) tuples.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all indexed chunks."""
        pass


class BM25Retriever(BaseKeywordRetriever):
    """
    Production-grade BM25Okapi implementation for lexical search.
    Provides term saturation, document length normalization, and metadata filtering.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.chunks: Dict[str, DocumentChunk] = {} # chunk_id -> DocumentChunk
        self.corpus_tokens: Dict[str, List[str]] = {} # chunk_id -> tokens
        self.doc_lengths: Dict[str, int] = {} # chunk_id -> length
        self.doc_freqs: Dict[str, int] = {} # term -> document frequency
        self.term_freqs: Dict[str, Counter] = {} # chunk_id -> Counter(terms)
        self.avg_doc_len: float = 0.0

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """
        Tokenize text into lowercase alphanumeric terms.
        Preserves technical terms, numbers, and identifiers.
        """
        if not text:
            return []
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\./#]+\b", text.lower())
        return tokens

    def _recalculate_stats(self) -> None:
        """Recalculate global document frequencies and average document length."""
        total_len = sum(self.doc_lengths.values())
        total_docs = len(self.chunks)
        self.avg_doc_len = (total_len / total_docs) if total_docs > 0 else 0.0

        # Recalculate document frequencies
        doc_freqs: Dict[str, int] = {}
        for chunk_id, tf in self.term_freqs.items():
            for term in tf.keys():
                doc_freqs[term] = doc_freqs.get(term, 0) + 1
        self.doc_freqs = doc_freqs

    def index_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Index or update chunks in the BM25 store."""
        if not chunks:
            return

        for chunk in chunks:
            tokens = self.tokenize(chunk.content)
            # Include section title and source name in tokens for higher recall
            extra_text = ""
            if chunk.metadata.section_title:
                extra_text += f" {chunk.metadata.section_title}"
            if chunk.metadata.source_name:
                extra_text += f" {chunk.metadata.source_name}"
            if chunk.metadata.sheet_name:
                extra_text += f" {chunk.metadata.sheet_name}"
            if extra_text:
                tokens.extend(self.tokenize(extra_text))

            self.chunks[chunk.chunk_id] = chunk
            self.corpus_tokens[chunk.chunk_id] = tokens
            self.doc_lengths[chunk.chunk_id] = len(tokens)
            self.term_freqs[chunk.chunk_id] = Counter(tokens)

        self._recalculate_stats()
        logger.info(f"BM25 index updated with {len(chunks)} chunks. Total documents: {len(self.chunks)}")

    def remove_document(self, document_id: str) -> None:
        """Remove all chunks associated with a document_id."""
        to_remove = [
            cid for cid, chunk in self.chunks.items()
            if chunk.metadata.document_id == document_id
        ]
        if not to_remove:
            return

        for cid in to_remove:
            self.chunks.pop(cid, None)
            self.corpus_tokens.pop(cid, None)
            self.doc_lengths.pop(cid, None)
            self.term_freqs.pop(cid, None)

        self._recalculate_stats()
        logger.info(f"BM25 removed {len(to_remove)} chunks for doc {document_id}. Remaining: {len(self.chunks)}")

    def clear(self) -> None:
        self.chunks.clear()
        self.corpus_tokens.clear()
        self.doc_lengths.clear()
        self.doc_freqs.clear()
        self.term_freqs.clear()
        self.avg_doc_len = 0.0

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Execute BM25 search with metadata filtering and normalized relevance scores.
        """
        if not self.chunks or not query.strip():
            return []

        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []

        n_docs = len(self.chunks)
        scores: Dict[str, float] = {}

        # 1. Filter eligible chunk IDs based on metadata
        eligible_chunk_ids: Set[str] = set()
        for chunk_id, chunk in self.chunks.items():
            if filters:
                match = True
                for k, v in filters.items():
                    if k == "workspace_id" and chunk.metadata.workspace_id != v:
                        match = False
                        break
                    elif k == "document_ids" and v is not None:
                        if chunk.metadata.document_id not in v:
                            match = False
                            break
                    elif k == "document_id" and chunk.metadata.document_id != v:
                        match = False
                        break
                    elif k == "source_type" and chunk.metadata.source_type != v:
                        match = False
                        break
                if not match:
                    continue
            eligible_chunk_ids.add(chunk_id)

        if not eligible_chunk_ids:
            return []

        # 2. Compute BM25Okapi scores for eligible chunks
        for term in query_tokens:
            df = self.doc_freqs.get(term, 0)
            if df == 0:
                continue

            # Standard Robertson-Spärck Jones IDF
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            if idf <= 0:
                idf = 0.01 # Prevent zero or negative weights for common terms

            for chunk_id in eligible_chunk_ids:
                tf = self.term_freqs[chunk_id].get(term, 0)
                if tf == 0:
                    continue
                doc_len = self.doc_lengths[chunk_id]
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                term_score = idf * (tf * (self.k1 + 1.0)) / denominator
                scores[chunk_id] = scores.get(chunk_id, 0.0) + term_score

        if not scores:
            return []

        # 3. Sort by score descending
        sorted_scored = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        max_score = sorted_scored[0][1] if sorted_scored else 1.0

        # 4. Normalize scores to [0.0, 1.0] range
        results: List[Tuple[DocumentChunk, float]] = []
        for chunk_id, raw_score in sorted_scored[:top_k]:
            normalized_score = raw_score / max_score if max_score > 0 else 0.0
            results.append((self.chunks[chunk_id], round(normalized_score, 4)))

        return results
