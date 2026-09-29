from typing import List, Optional
from backend.app.schemas.rag import ChatTurn
from backend.app.services.llm.base import BaseLLM
from backend.app.services.rag.prompts import QUERY_REWRITER_SYSTEM_PROMPT
from backend.app.core.logging import logger

class ConversationalQueryRewriter:
    """
    Transforms follow-up questions into standalone semantic search queries using conversation context.
    """

    def __init__(self, llm: Optional[BaseLLM] = None):
        self.llm = llm

    def rewrite(self, question: str, history: List[ChatTurn]) -> str:
        # If no history or LLM not configured, query is already standalone
        if not history or not self.llm:
            return question.strip()

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
                return cleaned
        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}. Falling back to original question.")

        return question.strip()
