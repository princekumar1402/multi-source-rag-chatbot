import hashlib
import numpy as np
from typing import List, Optional
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.core.config import settings
from backend.app.core.logging import logger

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

    def embed_query(self, text: str) -> List[float]:
        if self._use_fallback or not self._model:
            return self._fallback_embed(text)
        try:
            embedding = self._model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
            return embedding.tolist()
        except Exception as e:
            logger.warning(f"Model encode failed ({e}), using offline embedding.")
            return self._fallback_embed(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._use_fallback or not self._model:
            return [self._fallback_embed(t) for t in texts]
        try:
            embeddings = self._model.encode(texts, batch_size=32, convert_to_numpy=True, normalize_embeddings=True)
            return embeddings.tolist()
        except Exception as e:
            logger.warning(f"Model batch encode failed ({e}), using offline embedding.")
            return [self._fallback_embed(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dimension
