from typing import List, Tuple, Dict, Any, Optional
from backend.app.schemas.document import DocumentChunk
from backend.app.services.llm.base import BaseLLM
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.core.logging import logger

HYDE_PROMPT = """Please write a short, hypothetical passage that directly and factually answers the question.
Do not include any conversational filler or preambles.
Question: {question}
Hypothetical Answer:"""

class HyDERetriever:
    """
    Hypothetical Document Embeddings (HyDE) Retriever:
    Generates a hypothetical document using an LLM to bridge lexical/semantic gaps,
    then uses that hypothetical document for dense vector search.
    """

    def __init__(self, base_retriever: BaseRetriever, llm: Optional[BaseLLM] = None):
        self.base_retriever = base_retriever
        self.llm = llm

    def generate_hypothetical_document(self, query: str) -> str:
        if not self.llm:
            return query
        try:
            prompt = HYDE_PROMPT.format(question=query)
            hypothetical = self.llm.generate(prompt=prompt).strip()
            return hypothetical if hypothetical else query
        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}. Falling back to raw query.")
            return query

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        hypothetical_doc = self.generate_hypothetical_document(query)
        # Search using hypothetical document representation
        return self.base_retriever.retrieve(query=hypothetical_doc, top_k=top_k, filters=filters)
