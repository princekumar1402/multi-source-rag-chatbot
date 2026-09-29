from typing import List, Tuple, Optional, Set
from backend.app.schemas.document import DocumentChunk
from backend.app.core.config import settings
from backend.app.core.logging import logger

class ContextSelector:
    """
    Filters, deduplicates, and bounds retrieved chunks before LLM prompt assembly.
    Ensures zero metadata degradation for citations.
    """

    def __init__(
        self,
        min_relevance_score: float = 0.15,
        max_context_chunks: int = 6,
        overlap_threshold: float = 0.85
    ):
        self.min_relevance_score = min_relevance_score
        self.max_context_chunks = max_context_chunks
        self.overlap_threshold = overlap_threshold

    @staticmethod
    def _compute_overlap(text1: str, text2: str) -> float:
        """Computes Jaccard word-overlap similarity between two texts."""
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def select(
        self,
        candidates: List[Tuple[DocumentChunk, float]],
        max_chunks: Optional[int] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Applies score threshold, exact content deduplication, and high-overlap suppression.
        Returns final list of (DocumentChunk, score) tuples with 100% preserved metadata.
        """
        if not candidates:
            return []

        limit = max_chunks or self.max_context_chunks
        selected: List[Tuple[DocumentChunk, float]] = []
        seen_contents: Set[str] = set()

        for chunk, score in candidates:
            # 1. Relevance threshold
            if score < self.min_relevance_score:
                logger.debug(f"Chunk {chunk.chunk_id} dropped (score {score:.4f} < min {self.min_relevance_score})")
                continue

            cleaned_content = chunk.content.strip()
            # 2. Exact duplicate suppression
            if cleaned_content in seen_contents:
                logger.debug(f"Chunk {chunk.chunk_id} dropped as exact duplicate")
                continue

            # 3. Near-duplicate / excessive overlap suppression
            is_redundant = False
            for existing_chunk, _ in selected:
                overlap = self._compute_overlap(cleaned_content, existing_chunk.content)
                if overlap >= self.overlap_threshold:
                    logger.debug(
                        f"Chunk {chunk.chunk_id} dropped (overlap {overlap:.2f} >= {self.overlap_threshold})"
                    )
                    is_redundant = True
                    break

            if is_redundant:
                continue

            seen_contents.add(cleaned_content)
            selected.append((chunk, score))

            if len(selected) >= limit:
                break

        logger.info(f"ContextSelector: Filtered {len(candidates)} candidates down to {len(selected)} high-quality chunks")
        return selected
