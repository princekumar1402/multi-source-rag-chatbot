from abc import ABC, abstractmethod
from typing import Optional, Iterator

class BaseLLM(ABC):
    """
    Abstract interface for LLM inference.
    Enables swapping between Groq, OpenAI, Anthropic, or local Ollama.
    """

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate full text completion."""
        pass

    @abstractmethod
    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        """Generate token stream for real-time SSE output."""
        pass
