import re
from typing import List, Optional
from backend.app.schemas.rag import ChatTurn
from backend.app.services.llm.base import BaseLLM
from backend.app.services.rag.prompts import QUERY_REWRITER_SYSTEM_PROMPT
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.cache import cache_manager

class ConversationalQueryRewriter:
    """
    Transforms follow-up questions into standalone semantic search queries using conversation context.
    Features:
    - Bounded caching for identical questions + history turns
    - Fast coreference detection to bypass LLM when question is already standalone
    """

    COREFERENCE_PATTERN = re.compile(
        r"\b(it|its|they|them|their|theirs|this|that|these|those|he|him|his|she|her|hers|"
        r"what about|how about|why|which one|and then|earlier|previous|above|former|latter|same|again)\b",
        re.IGNORECASE
    )

    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm

    def is_conversational(self, question: str) -> bool:
        """Determines if the question likely depends on prior conversation context."""
        q_clean = question.strip().lower()
        # Very short questions or queries starting with connective phrases
        if len(q_clean.split()) <= 4:
            return True
        return bool(self.COREFERENCE_PATTERN.search(q_clean))

    def rewrite(self, question: str, history: List[ChatTurn]) -> str:
        # If no history or LLM not configured, query is already standalone
        if not history or not self.llm:
            return question.strip()

        # If question has no coreference signals and is self-contained, bypass rewrite
        if not self.is_conversational(question):
            return question.strip()

        model_name = getattr(self.llm, "model", "default")
        use_cache = getattr(settings, "QUERY_REWRITE_CACHE_ENABLED", True)

        if use_cache and not getattr(self.llm, "fail", False):
            cache_key = cache_manager.build_query_rewrite_key(question, history, model_name)
            cached = cache_manager.query_rewrite_cache.get(cache_key)
            if cached is not None:
                return cached

        # Format recent history (up to last 4 turns)
        recent_history = history[-4:]
        history_text = "\n".join([f"{turn.role.capitalize()}: {turn.content}" for turn in recent_history])

        prompt = f"""Conversation History:
{history_text}

Follow-up Question: {question}

Standalone Query:"""

        try:
            standalone = self.llm.generate(prompt=prompt, system_prompt=QUERY_REWRITER_SYSTEM_PROMPT).strip()
            # Clean any leading quotation marks or prefixes
            cleaned = standalone.strip('"\'')
            if cleaned:
                logger.info(f"Rewrote query '{question}' -> '{cleaned}'")
                if use_cache:
                    cache_manager.query_rewrite_cache.set(cache_key, cleaned)
                return cleaned
        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}. Falling back to original question.")

        return question.strip()
