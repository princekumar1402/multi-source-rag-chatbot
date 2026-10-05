from typing import List, Tuple, Dict, Any, Optional
from backend.app.schemas.document import DocumentChunk
from backend.app.schemas.rag import ChatTurn
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.services.rag.query_rewriter import ConversationalQueryRewriter
from backend.app.services.rag.confidence import RetrievalConfidenceAssessor, RetrievalConfidence, ConfidenceLevel
from backend.app.services.rag.multi_query import MultiQueryRetriever
from backend.app.core.logging import logger

class AdaptiveRetriever:
    """
    Intelligent Adaptive Retrieval Router:
    Classifies queries and dynamically selects the optimal retrieval pipeline:
    - CONVERSATIONAL: History resolution + query rewriting
    - HIGH CONFIDENCE: Fast hybrid retrieval without redundant passes
    - LOW / MEDIUM CONFIDENCE: Multi-query expansion + deep reranking
    """

    def __init__(
        self,
        base_retriever: BaseRetriever,
        query_rewriter: Optional[ConversationalQueryRewriter] = None,
        multi_query_retriever: Optional[MultiQueryRetriever] = None,
        confidence_assessor: Optional[RetrievalConfidenceAssessor] = None
    ):
        self.base_retriever = base_retriever
        self.query_rewriter = query_rewriter
        self.multi_query_retriever = multi_query_retriever
        self.confidence_assessor = confidence_assessor or RetrievalConfidenceAssessor()

    def route_and_retrieve(
        self,
        question: str,
        history: Optional[List[ChatTurn]] = None,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Tuple[DocumentChunk, float]], Dict[str, Any]]:
        routing_info: Dict[str, Any] = {
            "strategy": "direct_hybrid",
            "rewritten": False,
            "multi_query": False,
            "confidence": None
        }

        active_query = question.strip()
        # 1. Conversational routing check
        if history and self.query_rewriter and self.query_rewriter.is_conversational(question):
            active_query = self.query_rewriter.rewrite(question, history)
            routing_info["strategy"] = "conversational_rewrite"
            routing_info["rewritten"] = True
            routing_info["standalone_query"] = active_query

        # 2. Initial candidate retrieval
        candidates = self.base_retriever.retrieve(query=active_query, top_k=top_k * 2, filters=filters)

        # 3. Assess confidence
        confidence = self.confidence_assessor.assess(candidates)
        routing_info["confidence"] = confidence.model_dump()

        # 4. If confidence is LOW and multi-query is enabled, expand query
        if confidence.level == ConfidenceLevel.LOW and self.multi_query_retriever:
            logger.info(f"Low retrieval confidence ({confidence.score}) for '{active_query}'. Expanding via MultiQueryRetriever.")
            expanded_candidates = self.multi_query_retriever.retrieve(
                query=active_query,
                top_k=top_k * 2,
                filters=filters
            )
            if expanded_candidates:
                candidates = expanded_candidates
                routing_info["strategy"] = "expanded_multi_query"
                routing_info["multi_query"] = True

        return candidates[:top_k], routing_info
