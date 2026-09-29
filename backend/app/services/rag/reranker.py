import re
import math
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from collections import Counter

from backend.app.schemas.document import DocumentChunk
from backend.app.core.config import settings
from backend.app.core.logging import logger

class BaseReranker(ABC):
    """
    Abstract interface for cross-encoder reranking.
    Rescores candidate (DocumentChunk, score) tuples based on deep semantic relevance to query.
    """

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: List[Tuple[DocumentChunk, float]],
        top_k: int = 5
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Rerank candidate chunks according to relevance to query.
        Returns top_k (DocumentChunk, score) sorted descending by relevance score.
        """
        pass


class CrossEncoderReranker(BaseReranker):
    """
    Production Cross-Encoder Reranker using sentence-transformers CrossEncoder.
    Provides automatic fallback to an intelligent lexical-semantic rescorer
    if the cross-encoder model is unavailable, offline, or disabled.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        enabled: Optional[bool] = None,
        device: str = "cpu"
    ):
        self.model_name = model_name or getattr(settings, "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.enabled = enabled if enabled is not None else getattr(settings, "RERANKER_ENABLED", True)
        self.device = device
        self._model = None
        self._use_fallback = not self.enabled

        if self.enabled:
            self._init_model()

    def _init_model(self) -> None:
        try:
            logger.info(f"Loading CrossEncoder reranker: {self.model_name}")
            from sentence_transformers import CrossEncoder
            # Try to load model
            self._model = CrossEncoder(self.model_name, device=self.device)
            logger.info("CrossEncoder model loaded successfully.")
        except Exception as e:
            logger.warning(
                f"Could not load CrossEncoder model '{self.model_name}' ({e}). "
                "Activating intelligent lexical-semantic fallback reranker for zero-crash resilience."
            )
            self._use_fallback = True

    @staticmethod
    def _fallback_rescore(query: str, chunk: DocumentChunk, prior_score: float) -> float:
        """
        Intelligent lexical-semantic fallback rescorer.
        Computes query term coverage, bigrams, entity alignment, and title bonuses.
        """
        q_tokens = re.findall(r"\b[a-zA-Z0-9_\-\./#]+\b", query.lower())
        if not q_tokens:
            return prior_score

        content_lower = chunk.content.lower()
        title_lower = (chunk.metadata.section_title or "").lower() + " " + (chunk.metadata.source_name or "").lower()

        # Token coverage in content
        matches = sum(1 for t in q_tokens if t in content_lower)
        coverage = matches / len(q_tokens)

        # Bigram match bonus (e.g. "rahul sharma", "priya patel", "head-of-line blocking")
        bigrams = [f"{q_tokens[i]} {q_tokens[i+1]}" for i in range(len(q_tokens) - 1)]
        bigram_matches = sum(1 for bg in bigrams if bg in content_lower)
        bigram_bonus = min(0.35, bigram_matches * 0.15)

        # Title/Section bonus
        title_matches = sum(1 for t in q_tokens if t in title_lower)
        title_bonus = min(0.25, title_matches * 0.1)

        # Exact phrase match bonus
        phrase_bonus = 0.25 if query.lower().strip("?.! ") in content_lower else 0.0

        # Combine: 30% prior score + 40% token coverage + 30% phrase/bigram/title bonuses
        fused = (0.30 * prior_score) + (0.40 * coverage) + bigram_bonus + title_bonus + phrase_bonus
        return min(1.0, max(0.0, fused))

    def rerank(
        self,
        query: str,
        candidates: List[Tuple[DocumentChunk, float]],
        top_k: int = 5
    ) -> List[Tuple[DocumentChunk, float]]:
        if not candidates or not query.strip():
            return []

        # If only 1 candidate, return as is
        if len(candidates) == 1:
            return candidates[:top_k]

        # 1. Use deep cross-encoder if available
        if not self._use_fallback and self._model is not None:
            try:
                pairs = [[query, chunk.content] for chunk, _ in candidates]
                scores = self._model.predict(pairs)

                # Normalize scores with sigmoid or min-max
                rescored: List[Tuple[DocumentChunk, float]] = []
                for (chunk, _), raw_score in zip(candidates, scores):
                    # Sigmoid transform for unbounded logits
                    prob = 1.0 / (1.0 + math.exp(-float(raw_score)))
                    rescored.append((chunk, round(prob, 4)))

                rescored.sort(key=lambda x: x[1], reverse=True)
                return rescored[:top_k]
            except Exception as e:
                logger.warning(f"CrossEncoder prediction failed: {e}. Falling back to lexical-semantic rescorer.")

        # 2. Resilient fallback rescoring
        rescored = []
        for chunk, prior_score in candidates:
            score = self._fallback_rescore(query, chunk, prior_score)
            rescored.append((chunk, round(score, 4)))

        rescored.sort(key=lambda x: x[1], reverse=True)
        return rescored[:top_k]
