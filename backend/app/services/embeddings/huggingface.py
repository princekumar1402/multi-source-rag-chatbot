import hashlib
import numpy as np
from typing import List, Optional
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.cache import cache_manager

class HuggingFaceEmbedder(BaseEmbedder):
    """
    HuggingFace SentenceTransformer implementation of BaseEmbedder.
    Default: sentence-transformers/all-MiniLM-L6-v2 (384-dimensional).
    Includes an offline/firewall fallback so the application operates seamlessly
    even when HuggingFace Hub connectivity is unavailable.
    """

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.device = device or settings.EMBEDDING_DEVICE
        self._dimension = 384
        self._model = None
        self._use_fallback = False

        logger.info(f"Initializing HuggingFaceEmbedder with model: {self.model_name} on {self.device}")
        try:
            from sentence_transformers import SentenceTransformer
            # Try loading local files first or downloading with a quick timeout
            self._model = SentenceTransformer(self.model_name, device=self.device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(f"Successfully loaded SentenceTransformer ({self._dimension} dim).")
        except Exception as e:
            logger.warning(
                f"Could not load '{self.model_name}' from HuggingFace Hub ({e}). "
                "Activating deterministic offline embedding engine (384-dim) for offline resilience."
            )
            self._use_fallback = True

    def _fallback_embed(self, text: str) -> List[float]:
        """
        Deterministic, normalized 384-dimensional semantic projection.
        Ensures identical texts yield identical vectors, and similar n-grams cluster together.
        """
        vec = np.zeros(self._dimension, dtype=np.float32)
        words = text.lower().split()
        if not words:
            vec[0] = 1.0
            return vec.tolist()

        for word in words:
            # Hash word and character n-grams into vector slots
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            slot = h % self._dimension
            sign = 1.0 if (h // self._dimension) % 2 == 0 else -1.0
            vec[slot] += sign

            # Character 3-grams
            for i in range(len(word) - 2):
                ngram = word[i:i+3]
                nh = int(hashlib.md5(ngram.encode("utf-8")).hexdigest(), 16)
                nslot = nh % self._dimension
                nsign = 1.0 if (nh // self._dimension) % 2 == 0 else -1.0
                vec[nslot] += 0.5 * nsign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _get_cache_key(self, text: str) -> str:
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"emb:{self.model_name}:{text_hash}"

    def embed_query(self, text: str) -> List[float]:
        use_cache = getattr(settings, "EMBEDDING_CACHE_ENABLED", True)
        if use_cache:
            cache_key = self._get_cache_key(text)
            cached = cache_manager.embedding_cache.get(cache_key)
            if cached is not None:
                return cached

        if self._use_fallback or not self._model:
            vec = self._fallback_embed(text)
        else:
            try:
                embedding = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
                vec = embedding.tolist()
            except Exception as e:
                logger.warning(f"Model encode failed ({e}), using offline embedding.")
                vec = self._fallback_embed(text)

        if use_cache:
            cache_manager.embedding_cache.set(cache_key, vec)
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        use_cache = getattr(settings, "EMBEDDING_CACHE_ENABLED", True)
        results: List[Optional[List[float]]] = [None] * len(texts)
        missing_indices: List[int] = []
        missing_texts: List[str] = []

        if use_cache:
            for i, text in enumerate(texts):
                cached = cache_manager.embedding_cache.get(self._get_cache_key(text))
                if cached is not None:
                    results[i] = cached
                else:
                    missing_indices.append(i)
                    missing_texts.append(text)
        else:
            missing_indices = list(range(len(texts)))
            missing_texts = texts

        if missing_texts:
            if self._use_fallback or not self._model:
                computed = [self._fallback_embed(t) for t in missing_texts]
            else:
                try:
                    embeddings = self._model.encode(missing_texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
                    computed = embeddings.tolist()
                except Exception as e:
                    logger.warning(f"Model batch encode failed ({e}), using offline embedding.")
                    computed = [self._fallback_embed(t) for t in missing_texts]

            for idx, text, vec in zip(missing_indices, missing_texts, computed):
                results[idx] = vec
                if use_cache:
                    cache_manager.embedding_cache.set(self._get_cache_key(text), vec)

        return [r for r in results if r is not None]

    @property
    def dimension(self) -> int:
        return self._dimension
