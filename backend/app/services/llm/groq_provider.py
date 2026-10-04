import os
from typing import Optional, Iterator, Tuple, Dict, Any
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.services.llm.base import BaseLLM
from backend.app.core.config import settings
from backend.app.core.logging import logger

class GroqLLM(BaseLLM):
    """
    Groq implementation of BaseLLM using high-speed LPU inference.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        self.model = model or settings.GROQ_MODEL
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. LLM inference will fail until a key is provided in .env")
        self._llm = ChatGroq(
            api_key=self.api_key,
            model=self.model,
            temperature=settings.LLM_TEMPERATURE
        ) if self.api_key else None

    def _ensure_client(self):
        if not self._llm:
            api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY is missing. Please configure GROQ_API_KEY in your .env file.")
            self.api_key = api_key
            self._llm = ChatGroq(
                api_key=self.api_key,
                model=self.model,
                temperature=settings.LLM_TEMPERATURE
            )

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        self._ensure_client()
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        response = self._llm.invoke(messages)
        return str(response.content)

    def generate_with_metadata(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Tuple[str, Dict[str, Any]]:
        self._ensure_client()
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        response = self._llm.invoke(messages)
        meta = getattr(response, "response_metadata", {}) or {}
        token_usage = meta.get("token_usage", {}) or {}
        usage_info = {
            "model": meta.get("model_name", self.model),
            "input_tokens": token_usage.get("prompt_tokens"),
            "output_tokens": token_usage.get("completion_tokens"),
            "total_tokens": token_usage.get("total_tokens")
        }
        return str(response.content), usage_info

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        self._ensure_client()
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        for chunk in self._llm.stream(messages):
            if chunk.content:
                yield chunk.content

