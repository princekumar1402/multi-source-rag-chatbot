import re
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict

from backend.app.schemas.document import DocumentChunk
from backend.app.services.llm.base import BaseLLM
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.core.logging import logger

MULTI_QUERY_PROMPT = """You are an expert search query reformulator.
Given a user question, generate 3 distinct search query formulations:
1. Semantic rephrasing focusing on the core concept
2. Keyword-oriented formulation using high-information terms
3. Entity-specific formulation focusing on named entities or technical terms

Output exactly 3 lines, one query per line, with NO numbering, bullets, or explanations:
Question: {question}"""

class MultiQueryRetriever:
    """
    Expands difficult or ambiguous queries into multiple search formulations,
    retrieves candidates across each formulation, and combines them using
    Reciprocal Rank Fusion (RRF) with strict deduplication and document-scope isolation.
    """

    def __init__(self, base_retriever: BaseRetriever, llm: Optional[BaseLLM] = None, rrf_k: int = 60):
        self.base_retriever = base_retriever
        self.llm = llm
        self.rrf_k = rrf_k

    def generate_variants(self, query: str) -> List[str]:
        variants = [query.strip()]
        if not self.llm:
            # Deterministic fallback variants
            words = [w for w in re.findall(r"\b\w+\b", query) if len(w) > 3]
            if len(words) >= 3:
                variants.append(" ".join(words)) # keyword formulation
            return variants

        try:
            prompt = MULTI_QUERY_PROMPT.format(question=query)
            raw = self.llm.generate(prompt=prompt)
            lines = [l.strip().strip("-*123. ") for l in raw.strip().split("\n") if l.strip()]
            for line in lines[:3]:
                if line and line.lower() not in [v.lower() for v in variants]:
                    variants.append(line)
        except Exception as e:
            logger.warning(f"Multi-query generation failed: {e}. Using original query.")

        return variants

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        variants = self.generate_variants(query)
        logger.info(f"MultiQueryRetriever expanding '{query}' into {len(variants)} formulations: {variants}")

        rrf_scores: Dict[str, float] = defaultdict(float)
        chunk_map: Dict[str, DocumentChunk] = {}

        for variant in variants:
            candidates = self.base_retriever.retrieve(query=variant, top_k=top_k * 2, filters=filters)
            for rank, (chunk, _) in enumerate(candidates, start=1):
                chunk_map[chunk.chunk_id] = chunk
                rrf_scores[chunk.chunk_id] += 1.0 / (self.rrf_k + rank)

        # Sort merged candidates by reciprocal rank score
        merged = sorted(
            [(chunk_map[cid], score) for cid, score in rrf_scores.items()],
            key=lambda x: x[1],
            reverse=True
        )

        return merged[:top_k]
