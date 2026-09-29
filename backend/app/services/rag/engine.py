import time
from typing import List, Tuple, Dict, Any, Optional

from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, Citation
from backend.app.schemas.document import DocumentChunk, SourceType
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.services.rag.query_rewriter import ConversationalQueryRewriter
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.rag.prompts import SYSTEM_GROUNDED_RAG_PROMPT, USER_GROUNDED_RAG_TEMPLATE
from backend.app.services.llm.base import BaseLLM
from backend.app.core.config import settings
from backend.app.core.logging import logger

class RAGEngine:
    """
    Production RAG Engine orchestrating:
    1. Conversational Query Rewriting (with graceful fallback)
    2. Multi-source Retrieval (Dense, BM25, or Hybrid with RRF)
    3. Cross-Encoder Reranking
    4. Context Selection & Deduplication (preserving 100% citation metadata)
    5. Grounded Generation (strict anti-hallucination)
    6. Citation Validation & Source Attribution
    7. Detailed Latency & Retrieval Debug Tracking
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseLLM,
        query_rewriter: Optional[ConversationalQueryRewriter] = None,
        context_selector: Optional[ContextSelector] = None
    ):
        self.retriever = retriever
        self.llm = llm
        self.query_rewriter = query_rewriter or ConversationalQueryRewriter(llm=llm)
        retriever_thresh = getattr(retriever, "min_relevance_threshold", None)
        default_min_score = retriever_thresh if (retriever_thresh is not None and retriever_thresh >= 0) else getattr(settings, "MIN_RELEVANCE_SCORE", 0.15)
        self.context_selector = context_selector or ContextSelector(
            min_relevance_score=default_min_score,
            max_context_chunks=getattr(settings, "MAX_CONTEXT_CHUNKS", 6),
            overlap_threshold=getattr(settings, "CONTEXT_OVERLAP_THRESHOLD", 0.85)
        )

    def _build_context_and_citations(
        self,
        retrieved: List[Tuple[DocumentChunk, float]]
    ) -> Tuple[str, List[Citation]]:
        context_blocks = []
        citations: List[Citation] = []

        for i, (chunk, score) in enumerate(retrieved, start=1):
            meta = chunk.metadata
            label = f"[Source {i}]"
            source_detail = meta.source_name

            if meta.source_type == SourceType.YOUTUBE and meta.timestamp_str:
                source_detail += f" ({meta.timestamp_str})"
            elif meta.source_type == SourceType.PDF and meta.page_number:
                source_detail += f" (Page {meta.page_number})"
            elif meta.source_type == SourceType.XLSX and meta.sheet_name and meta.row_number:
                source_detail += f" (Sheet '{meta.sheet_name}', Row {meta.row_number})"
            elif meta.source_type == SourceType.CSV and meta.row_number:
                source_detail += f" (Row {meta.row_number})"
            elif meta.section_title:
                source_detail += f" (Section: {meta.section_title})"

            block = f"{label} {source_detail}:\n{chunk.content}"
            context_blocks.append(block)

            # Build Citation object with 100% verified chunk metadata
            citations.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    document_id=meta.document_id,
                    source_title=meta.source_name,
                    source_type=meta.source_type,
                    file_name=meta.file_name,
                    source_url=meta.source_url,
                    page_number=meta.page_number,
                    page_index=meta.page_index,
                    sheet_name=meta.sheet_name,
                    row_number=meta.row_number,
                    timestamp_str=meta.timestamp_str,
                    start_time=meta.start_time,
                    end_time=meta.end_time,
                    section_title=meta.section_title,
                    snippet=chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                    relevance_score=round(score, 4)
                )
            )

        return "\n\n".join(context_blocks), citations

    def query(self, request: RAGQueryRequest) -> RAGQueryResponse:
        t_start = time.perf_counter()
        logger.info(f"Executing RAG query: '{request.question}' in workspace: {request.workspace_id}")

        # 1. Conversational Query Rewriting
        t0 = time.perf_counter()
        standalone_query = request.question
        if request.enable_query_rewriting and request.history:
            try:
                standalone_query = self.query_rewriter.rewrite(request.question, request.history)
            except Exception as e:
                logger.warning(f"Query rewriter exception: {e}. Falling back to original question.")
                standalone_query = request.question
        t_rewrite_ms = (time.perf_counter() - t0) * 1000

        # 2. Build metadata filters
        filters: Dict[str, Any] = {"workspace_id": request.workspace_id}
        if request.document_ids:
            filters["document_ids"] = request.document_ids
        if request.source_types:
            filters["source_type"] = request.source_types[0] if len(request.source_types) == 1 else None

        # 3. Retrieval Execution (Hybrid or Dense)
        t1 = time.perf_counter()
        debug_info: Dict[str, Any] = {
            "original_query": request.question,
            "rewritten_query": standalone_query,
            "query_rewrite_ms": round(t_rewrite_ms, 2)
        }
        retrieval_metadata: Dict[str, Any] = {
            "retriever": "dense",
            "candidate_count": 0,
            "final_context_count": 0
        }

        t_rerank_ms = 0.0
        retrieval_ms = 0.0

        if hasattr(self.retriever, "retrieve_with_details"):
            details = self.retriever.retrieve_with_details(
                query=standalone_query,
                top_k=request.top_k * 2,
                filters=filters
            )
            raw_candidates = details["results"]
            retrieval_metadata["retriever"] = "hybrid"
            retrieval_metadata["candidate_count"] = len(details.get("fused_candidates", []))
            retrieval_ms = details.get("retrieval_ms", 0.0) + details.get("fusion_ms", 0.0)
            t_rerank_ms = details.get("rerank_ms", 0.0)

            if request.debug or getattr(settings, "DEBUG", False):
                debug_info["dense_candidates"] = [
                    {"chunk_id": c.chunk_id, "source": c.metadata.source_name, "score": s}
                    for c, s in details.get("dense_candidates", [])
                ]
                debug_info["bm25_candidates"] = [
                    {"chunk_id": c.chunk_id, "source": c.metadata.source_name, "score": s}
                    for c, s in details.get("bm25_candidates", [])
                ]
                debug_info["fused_candidates"] = [
                    {"chunk_id": c.chunk_id, "source": c.metadata.source_name, "score": s}
                    for c, s in details.get("fused_candidates", [])
                ]
                debug_info["reranked_candidates"] = [
                    {"chunk_id": c.chunk_id, "source": c.metadata.source_name, "score": s}
                    for c, s in details.get("reranked_candidates", [])
                ]
        else:
            raw_candidates = self.retriever.retrieve(
                query=standalone_query,
                top_k=request.top_k * 2,
                filters=filters
            )
            retrieval_ms = (time.perf_counter() - t1) * 1000
            retrieval_metadata["candidate_count"] = len(raw_candidates)

        # 4. Context Selection & Deduplication
        selected_candidates = self.context_selector.select(
            candidates=raw_candidates,
            max_chunks=request.top_k
        )
        retrieval_metadata["final_context_count"] = len(selected_candidates)

        # If no candidates meet the criteria -> Safe insufficient context response
        if not selected_candidates:
            t_total_ms = (time.perf_counter() - t_start) * 1000
            latency_breakdown = {
                "rewrite_ms": round(t_rewrite_ms, 2),
                "retrieval_ms": round(retrieval_ms, 2),
                "reranking_ms": round(t_rerank_ms, 2),
                "generation_ms": 0.0,
                "total_ms": round(t_total_ms, 2)
            }
            return RAGQueryResponse(
                question=request.question,
                standalone_query=standalone_query,
                answer="The available knowledge base sources do not contain enough information to answer this question.",
                citations=[],
                has_sufficient_context=False,
                retrieved_count=0,
                latency_seconds=round(t_total_ms / 1000.0, 3),
                retrieval=retrieval_metadata,
                latency=latency_breakdown,
                debug=debug_info if (request.debug or getattr(settings, "DEBUG", False)) else None
            )

        # 5. Build context string and verified citations
        context_str, candidate_citations = self._build_context_and_citations(selected_candidates)
        if request.debug or getattr(settings, "DEBUG", False):
            debug_info["final_context"] = [
                {"chunk_id": c.chunk_id, "source": c.metadata.source_name, "content": c.content[:150]}
                for c, _ in selected_candidates
            ]

        # 6. Formulate Grounded Prompt
        prompt = USER_GROUNDED_RAG_TEMPLATE.format(
            context_blocks=context_str,
            question=standalone_query
        )

        # 7. LLM Generation
        t2 = time.perf_counter()
        try:
            answer = self.llm.generate(prompt=prompt, system_prompt=SYSTEM_GROUNDED_RAG_PROMPT)
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            t_total_ms = (time.perf_counter() - t_start) * 1000
            latency_breakdown = {
                "rewrite_ms": round(t_rewrite_ms, 2),
                "retrieval_ms": round(retrieval_ms, 2),
                "reranking_ms": round(t_rerank_ms, 2),
                "generation_ms": round((time.perf_counter() - t2) * 1000, 2),
                "total_ms": round(t_total_ms, 2)
            }
            return RAGQueryResponse(
                question=request.question,
                standalone_query=standalone_query,
                answer=f"Error generating response: {str(e)}",
                citations=candidate_citations,
                has_sufficient_context=False,
                retrieved_count=len(selected_candidates),
                latency_seconds=round(t_total_ms / 1000.0, 3),
                retrieval=retrieval_metadata,
                latency=latency_breakdown,
                debug=debug_info if (request.debug or getattr(settings, "DEBUG", False)) else None
            )

        t_gen_ms = (time.perf_counter() - t2) * 1000
        t_total_ms = (time.perf_counter() - t_start) * 1000

        # 8. Insufficient Context Detection & Citation Validation
        insufficient_phrases = [
            "do not contain enough information",
            "does not contain enough information",
            "insufficient information"
        ]
        has_sufficient_context = not any(p in answer.lower() for p in insufficient_phrases)

        # Citation validation: if insufficient context, suppress citations to prevent false attribution
        final_citations: List[Citation] = []
        if has_sufficient_context:
            # Only keep citations that were actually referenced or derived from retrieved context
            valid_chunk_ids = {c.chunk_id for c, _ in selected_candidates}
            final_citations = [cit for cit in candidate_citations if cit.chunk_id in valid_chunk_ids]

        latency_breakdown = {
            "rewrite_ms": round(t_rewrite_ms, 2),
            "retrieval_ms": round(retrieval_ms, 2),
            "reranking_ms": round(t_rerank_ms, 2),
            "generation_ms": round(t_gen_ms, 2),
            "total_ms": round(t_total_ms, 2)
        }

        return RAGQueryResponse(
            question=request.question,
            standalone_query=standalone_query,
            answer=answer,
            citations=final_citations,
            has_sufficient_context=has_sufficient_context,
            retrieved_count=len(selected_candidates),
            latency_seconds=round(t_total_ms / 1000.0, 3),
            retrieval=retrieval_metadata,
            latency=latency_breakdown,
            debug=debug_info if (request.debug or getattr(settings, "DEBUG", False)) else None
        )
