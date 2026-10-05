import re
import math
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from collections import Counter

from backend.app.schemas.document import DocumentChunk
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.cache import cache_manager

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

    ENGLISH_STOP_WORDS = {
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
        "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
        "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
        "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
        "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
        "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
        "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
        "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
        "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
        "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
        "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
        "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
        "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
        "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
        "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
        "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
        "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's",
        "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
        "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
    }

    @classmethod
    def _fallback_rescore(cls, query: str, chunk: DocumentChunk, prior_score: float) -> float:
        """
        Intelligent lexical-semantic fallback rescorer.
        Computes query term coverage, bigrams, entity alignment, and title bonuses,
        filtering out common stopwords to avoid ranking inversion.
        """
        raw_tokens = re.findall(r"\b[a-zA-Z0-9_\-\./#]+\b", query.lower())
        q_tokens = [t for t in raw_tokens if t not in cls.ENGLISH_STOP_WORDS and len(t) > 1]
        if not q_tokens:
            q_tokens = raw_tokens
        if not q_tokens:
            return prior_score

        content_lower = chunk.content.lower()
        title_lower = (chunk.metadata.section_title or "").lower() + " " + (chunk.metadata.source_name or "").lower()

        def _token_match(token: str, text: str) -> bool:
            if token in text:
                return True
            stem = token.rstrip("es").rstrip("s").rstrip("ing").rstrip("ed")
            return len(stem) >= 3 and stem in text

        # Token coverage in content
        matches = sum(1 for t in q_tokens if _token_match(t, content_lower))
        coverage = matches / len(q_tokens)

        # Bigram match bonus (e.g. "rahul sharma", "priya patel", "dark chocolate")
        bigrams = [f"{q_tokens[i]} {q_tokens[i+1]}" for i in range(len(q_tokens) - 1)]
        bigram_matches = sum(1 for bg in bigrams if bg in content_lower)
        bigram_bonus = min(0.35, bigram_matches * 0.15)

        # Title/Section bonus
        title_matches = sum(1 for t in q_tokens if _token_match(t, title_lower))
        title_bonus = min(0.25, title_matches * 0.1)

        # Exact phrase match bonus
        clean_q = query.lower().strip("?.! ")
        phrase_bonus = 0.25 if clean_q in content_lower else 0.0

        # Combine: 35% prior score + 45% token coverage + 20% phrase/bigram/title bonuses
        fused = (0.35 * prior_score) + (0.45 * coverage) + bigram_bonus + title_bonus + phrase_bonus
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

        use_cache = getattr(settings, "RERANKER_CACHE_ENABLED", True)
        import hashlib
        q_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()

        # 1. Use deep cross-encoder if available
        if not self._use_fallback and self._model is not None:
            try:
                rescored: List[Tuple[DocumentChunk, float]] = []
                missing_indices = []
                missing_pairs = []

                if use_cache:
                    for idx, (chunk, prior_score) in enumerate(candidates):
                        ckey = f"rerank:ce:{q_hash}:{chunk.chunk_id}"
                        cached = cache_manager.reranker_cache.get(ckey)
                        if cached is not None:
                            rescored.append((chunk, cached))
                        else:
                            missing_indices.append(idx)
                            missing_pairs.append([query, chunk.content])
                else:
                    missing_indices = list(range(len(candidates)))
                    missing_pairs = [[query, chunk.content] for chunk, _ in candidates]

                if missing_pairs:
                    scores = self._model.predict(missing_pairs)
                    for (m_idx, raw_score) in zip(missing_indices, scores):
                        chunk, _ = candidates[m_idx]
                        prob = 1.0 / (1.0 + math.exp(-float(raw_score)))
                        score_rounded = round(prob, 4)
                        rescored.append((chunk, score_rounded))
                        if use_cache:
                            cache_manager.reranker_cache.set(f"rerank:ce:{q_hash}:{chunk.chunk_id}", score_rounded)

                rescored.sort(key=lambda x: x[1], reverse=True)
                return rescored[:top_k]
            except Exception as e:
                logger.warning(f"CrossEncoder prediction failed: {e}. Falling back to lexical-semantic rescorer.")

        # 2. Resilient fallback rescoring
        rescored = []
        for chunk, prior_score in candidates:
            ckey = f"rerank:fb:{q_hash}:{chunk.chunk_id}"
            if use_cache:
                cached = cache_manager.reranker_cache.get(ckey)
                if cached is not None:
                    rescored.append((chunk, cached))
                    continue

            score = self._fallback_rescore(query, chunk, prior_score)
            score_rounded = round(score, 4)
            rescored.append((chunk, score_rounded))
            if use_cache:
                cache_manager.reranker_cache.set(ckey, score_rounded)

        rescored.sort(key=lambda x: x[1], reverse=True)
        return rescored[:top_k]
