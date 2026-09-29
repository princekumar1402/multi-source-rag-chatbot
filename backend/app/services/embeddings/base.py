from abc import ABC, abstractmethod
from typing import List

class BaseEmbedder(ABC):
    """
    Abstract interface for embedding generation.
    Enables zero-cost local HuggingFace embeddings or pluggable OpenAI / Ollama providers.
    """
    
    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single search query."""
        pass

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of document texts."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass
