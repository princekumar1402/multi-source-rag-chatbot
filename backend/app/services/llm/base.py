from abc import ABC, abstractmethod
from typing import Optional, Iterator, Tuple, Dict, Any

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

    def generate_with_metadata(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate full text completion with optional token usage and model metadata."""
        content = self.generate(prompt, system_prompt)
        return content, {
            "model": getattr(self, "model", "unknown"),
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None
        }

