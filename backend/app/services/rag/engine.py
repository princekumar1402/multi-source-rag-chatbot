import time
import json
import uuid
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
from backend.app.core.cache import cache_manager

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
        trace_id = getattr(request, "trace_id", None) or str(uuid.uuid4())
        logger.info(f"Executing RAG query: '{request.question}' [trace_id={trace_id}] in workspace: {request.workspace_id}")

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

        # 2. Check Answer Cache (Full RAG Response Cache)
        t_cache_start = time.perf_counter()
        ans_cache_enabled = getattr(settings, "ANSWER_CACHE_ENABLED", True)
        ans_key = None
        model_name = getattr(self.llm, "model", "default")
        temperature = getattr(settings, "LLM_TEMPERATURE", 0.0)

        if ans_cache_enabled and request.workspace_id:
            ans_key = cache_manager.build_answer_cache_key(
                workspace_id=request.workspace_id,
                query=standalone_query,
                document_ids=request.document_ids,
                model_name=model_name,
                temperature=temperature,
                top_k=request.top_k
            )
            cached_resp = cache_manager.answer_cache.get(ans_key)
            if cached_resp is not None:
                t_cache_ms = (time.perf_counter() - t_cache_start) * 1000
                t_total_ms = (time.perf_counter() - t_start) * 1000

                trace_copy = dict(cached_resp.trace) if cached_resp.trace else {}
                trace_copy.update({
                    "trace_id": trace_id,
                    "query_id": trace_id,
                    "query_rewriting_latency_ms": round(t_rewrite_ms, 2),
                    "cache_lookup_latency_ms": round(t_cache_ms, 2),
                    "total_latency_ms": round(t_total_ms, 2),
                    "cache_hit": True,
                    "cache_stage": "answer"
                })

                logger.info(json.dumps({
                    "event": "rag_request_completed",
                    "trace_id": trace_id,
                    "total_latency_ms": round(t_total_ms, 2),
                    "retrieved_chunks": cached_resp.retrieved_count,
                    "context_chunks": cached_resp.retrieved_count,
                    "citations": len(cached_resp.citations),
                    "model": model_name,
                    "has_sufficient_context": cached_resp.has_sufficient_context,
                    "cache_hit": True,
                    "cache_stage": "answer"
                }))

                return RAGQueryResponse(
                    question=request.question,
                    standalone_query=standalone_query,
                    answer=cached_resp.answer,
                    citations=cached_resp.citations,
                    has_sufficient_context=cached_resp.has_sufficient_context,
                    retrieved_count=cached_resp.retrieved_count,
                    latency_seconds=round(t_total_ms / 1000.0, 3),
                    retrieval=cached_resp.retrieval,
                    latency={
                        "rewrite_ms": round(t_rewrite_ms, 2),
                        "retrieval_ms": 0.0,
                        "reranking_ms": 0.0,
                        "generation_ms": 0.0,
                        "total_ms": round(t_total_ms, 2)
                    },
                    trace_id=trace_id,
                    trace=trace_copy,
                    tokens=cached_resp.tokens,
                    debug=cached_resp.debug
                )

        t_cache_lookup_ms = (time.perf_counter() - t_cache_start) * 1000

        # 3. Build metadata filters
        t_filter_start = time.perf_counter()
        filters: Dict[str, Any] = {"workspace_id": request.workspace_id}
        if request.document_ids:
            filters["document_ids"] = request.document_ids
        if request.source_types:
            filters["source_type"] = request.source_types[0] if len(request.source_types) == 1 else None
        t_filter_ms = (time.perf_counter() - t_filter_start) * 1000

        # 4. Retrieval Execution (with Retrieval Cache)
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

        dense_retrieval_ms = 0.0
        bm25_retrieval_ms = 0.0
        rrf_fusion_ms = 0.0
        t_rerank_ms = 0.0
        retrieval_ms = 0.0

        dense_count = 0
        bm25_count = 0
        fused_count = 0
        reranked_count = 0

        ret_cache_enabled = getattr(settings, "RETRIEVAL_CACHE_ENABLED", True)
        ret_key = None
        cached_ret = None
        cache_stage = "none"
        cache_hit = False

        if ret_cache_enabled and request.workspace_id:
            ret_key = cache_manager.build_retrieval_cache_key(
                workspace_id=request.workspace_id,
                query=standalone_query,
                document_ids=request.document_ids,
                source_types=request.source_types,
                top_k=request.top_k * 2
            )
            cached_ret = cache_manager.retrieval_cache.get(ret_key)

        try:
            if cached_ret is not None:
                raw_candidates = cached_ret["results"]
                retrieval_metadata = cached_ret["retrieval_metadata"]
                dense_count = cached_ret.get("dense_count", len(raw_candidates))
                bm25_count = cached_ret.get("bm25_count", len(raw_candidates))
                fused_count = cached_ret.get("fused_count", len(raw_candidates))
                reranked_count = cached_ret.get("reranked_count", len(raw_candidates))
                cache_hit = True
                cache_stage = "retrieval"
                retrieval_ms = (time.perf_counter() - t1) * 1000
            elif hasattr(self.retriever, "retrieve_with_details"):
                details = self.retriever.retrieve_with_details(
                    query=standalone_query,
                    top_k=request.top_k * 2,
                    filters=filters
                )
                raw_candidates = details["results"]
                retrieval_metadata["retriever"] = "hybrid"
                retrieval_metadata["candidate_count"] = len(details.get("fused_candidates", []))
                dense_retrieval_ms = details.get("dense_ms", 0.0)
                bm25_retrieval_ms = details.get("bm25_ms", 0.0)
                rrf_fusion_ms = details.get("fusion_ms", 0.0)
                retrieval_ms = details.get("retrieval_ms", 0.0) + rrf_fusion_ms
                t_rerank_ms = details.get("rerank_ms", 0.0)

                dense_count = len(details.get("dense_candidates", []))
                bm25_count = len(details.get("bm25_candidates", []))
                fused_count = len(details.get("fused_candidates", []))
                reranked_count = len(details.get("reranked_candidates", []))

                if ret_cache_enabled and ret_key:
                    cache_manager.retrieval_cache.set(
                        ret_key,
                        {
                            "results": raw_candidates,
                            "retrieval_metadata": dict(retrieval_metadata),
                            "dense_count": dense_count,
                            "bm25_count": bm25_count,
                            "fused_count": fused_count,
                            "reranked_count": reranked_count
                        },
                        tag=request.workspace_id
                    )

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
                dense_retrieval_ms = retrieval_ms
                retrieval_metadata["candidate_count"] = len(raw_candidates)
                dense_count = len(raw_candidates)
                fused_count = len(raw_candidates)
                reranked_count = len(raw_candidates)

                if ret_cache_enabled and ret_key:
                    cache_manager.retrieval_cache.set(
                        ret_key,
                        {
                            "results": raw_candidates,
                            "retrieval_metadata": dict(retrieval_metadata),
                            "dense_count": dense_count,
                            "bm25_count": bm25_count,
                            "fused_count": fused_count,
                            "reranked_count": reranked_count
                        },
                        tag=request.workspace_id
                    )
        except Exception as e:
            logger.error(json.dumps({
                "event": "rag_request_failed",
                "trace_id": trace_id,
                "stage": "retrieval",
                "error_type": type(e).__name__
            }))
            raise

        # 5. Context Selection & Deduplication
        t_sel_start = time.perf_counter()
        selected_candidates = self.context_selector.select(
            candidates=raw_candidates,
            max_chunks=request.top_k
        )
        t_sel_ms = (time.perf_counter() - t_sel_start) * 1000
        retrieval_metadata["final_context_count"] = len(selected_candidates)

        # Score stats helper
        scores = [round(float(s), 4) for _, s in selected_candidates]
        score_stats = {
            "min_score": min(scores) if scores else 0.0,
            "max_score": max(scores) if scores else 0.0,
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0
        }

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
            trace_data = {
                "trace_id": trace_id,
                "query_id": trace_id,
                "query_rewriting_latency_ms": round(t_rewrite_ms, 2),
                "cache_lookup_latency_ms": round(t_cache_lookup_ms, 2),
                "metadata_filtering_latency_ms": round(t_filter_ms, 2),
                "dense_retrieval_latency_ms": round(dense_retrieval_ms, 2),
                "bm25_retrieval_latency_ms": round(bm25_retrieval_ms, 2),
                "rrf_fusion_latency_ms": round(rrf_fusion_ms, 2),
                "reranking_latency_ms": round(t_rerank_ms, 2),
                "context_selection_latency_ms": round(t_sel_ms, 2),
                "prompt_construction_latency_ms": 0.0,
                "llm_latency_ms": 0.0,
                "citation_validation_latency_ms": 0.0,
                "total_latency_ms": round(t_total_ms, 2),
                "cache_hit": cache_hit,
                "cache_stage": cache_stage,
                "retrieval_metrics": {
                    "dense_candidate_count": dense_count,
                    "bm25_candidate_count": bm25_count,
                    "rrf_candidate_count": fused_count,
                    "reranked_candidate_count": reranked_count,
                    "final_context_count": 0,
                    "selected_document_ids": request.document_ids or [],
                    "score_statistics": score_stats
                }
            }

            logger.info(json.dumps({
                "event": "rag_request_completed",
                "trace_id": trace_id,
                "total_latency_ms": round(t_total_ms, 2),
                "retrieved_chunks": 0,
                "context_chunks": 0,
                "citations": 0,
                "model": getattr(self.llm, "model", None),
                "has_sufficient_context": False,
                "cache_hit": cache_hit,
                "cache_stage": cache_stage
            }))

            insufficient_resp = RAGQueryResponse(
                question=request.question,
                standalone_query=standalone_query,
                answer="The available knowledge base sources do not contain enough information to answer this question.",
                citations=[],
                has_sufficient_context=False,
                retrieved_count=0,
                latency_seconds=round(t_total_ms / 1000.0, 3),
                retrieval=retrieval_metadata,
                latency=latency_breakdown,
                trace_id=trace_id,
                trace=trace_data,
                tokens=None,
                debug=debug_info if (request.debug or getattr(settings, "DEBUG", False)) else None
            )
            if ans_cache_enabled and ans_key:
                cache_manager.answer_cache.set(ans_key, insufficient_resp, tag=request.workspace_id)
            return insufficient_resp

        # 6. Build context string and verified citations
        context_str, candidate_citations = self._build_context_and_citations(selected_candidates)
        if request.debug or getattr(settings, "DEBUG", False):
            debug_info["final_context"] = [
                {"chunk_id": c.chunk_id, "source": c.metadata.source_name, "content": c.content[:150]}
                for c, _ in selected_candidates
            ]

        # 7. Formulate Grounded Prompt
        t_prompt_start = time.perf_counter()
        prompt = USER_GROUNDED_RAG_TEMPLATE.format(
            context_blocks=context_str,
            question=standalone_query
        )
        t_prompt_ms = (time.perf_counter() - t_prompt_start) * 1000

        # 8. LLM Generation
        t2 = time.perf_counter()
        token_usage_dict: Optional[Dict[str, Any]] = None
        llm_model_name: Optional[str] = getattr(self.llm, "model", None)
        try:
            if hasattr(self.llm, "generate_with_metadata"):
                answer, gen_meta = self.llm.generate_with_metadata(prompt=prompt, system_prompt=SYSTEM_GROUNDED_RAG_PROMPT)
                if gen_meta:
                    llm_model_name = gen_meta.get("model", llm_model_name)
                    token_usage_dict = gen_meta.get("token_usage", None)
            else:
                answer = self.llm.generate(prompt=prompt, system_prompt=SYSTEM_GROUNDED_RAG_PROMPT)
        except Exception as e:
            logger.error(json.dumps({
                "event": "rag_request_failed",
                "trace_id": trace_id,
                "stage": "llm_generation",
                "error_type": type(e).__name__
            }))
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
                trace_id=trace_id,
                trace=None,
                tokens=None,
                debug=debug_info if (request.debug or getattr(settings, "DEBUG", False)) else None
            )

        t_gen_ms = (time.perf_counter() - t2) * 1000

        # 9. Insufficient Context Detection & Citation Validation
        t_cite_start = time.perf_counter()
        insufficient_phrases = [
            "do not contain enough information",
            "does not contain enough information",
            "insufficient information"
        ]
        has_sufficient_context = not any(p in answer.lower() for p in insufficient_phrases)

        # Citation validation: if insufficient context, suppress citations to prevent false attribution
        final_citations: List[Citation] = []
        if has_sufficient_context:
            valid_chunk_ids = {c.chunk_id for c, _ in selected_candidates}
            final_citations = [cit for cit in candidate_citations if cit.chunk_id in valid_chunk_ids]
        t_cite_ms = (time.perf_counter() - t_cite_start) * 1000

        t_total_ms = (time.perf_counter() - t_start) * 1000

        latency_breakdown = {
            "rewrite_ms": round(t_rewrite_ms, 2),
            "retrieval_ms": round(retrieval_ms, 2),
            "reranking_ms": round(t_rerank_ms, 2),
            "generation_ms": round(t_gen_ms, 2),
            "total_ms": round(t_total_ms, 2)
        }

        trace_data = {
            "trace_id": trace_id,
            "query_id": trace_id,
            "query_rewriting_latency_ms": round(t_rewrite_ms, 2),
            "cache_lookup_latency_ms": round(t_cache_lookup_ms, 2),
            "metadata_filtering_latency_ms": round(t_filter_ms, 2),
            "dense_retrieval_latency_ms": round(dense_retrieval_ms, 2),
            "bm25_retrieval_latency_ms": round(bm25_retrieval_ms, 2),
            "rrf_fusion_latency_ms": round(rrf_fusion_ms, 2),
            "reranking_latency_ms": round(t_rerank_ms, 2),
            "context_selection_latency_ms": round(t_sel_ms, 2),
            "prompt_construction_latency_ms": round(t_prompt_ms, 2),
            "llm_latency_ms": round(t_gen_ms, 2),
            "citation_validation_latency_ms": round(t_cite_ms, 2),
            "total_latency_ms": round(t_total_ms, 2),
            "cache_hit": cache_hit,
            "cache_stage": cache_stage,
            "retrieval_metrics": {
                "dense_candidate_count": dense_count,
                "bm25_candidate_count": bm25_count,
                "rrf_candidate_count": fused_count,
                "reranked_candidate_count": reranked_count,
                "final_context_count": len(selected_candidates),
                "selected_document_ids": list(set(c.metadata.document_id for c, _ in selected_candidates)),
                "score_statistics": score_stats
            }
        }

        # Token telemetry
        tokens_telemetry: Optional[Dict[str, Any]] = None
        if token_usage_dict:
            tokens_telemetry = {
                "model": llm_model_name,
                "input_tokens": token_usage_dict.get("prompt_tokens"),
                "output_tokens": token_usage_dict.get("completion_tokens"),
                "total_tokens": token_usage_dict.get("total_tokens"),
                "generation_latency_ms": round(t_gen_ms, 2)
            }
        elif llm_model_name:
            tokens_telemetry = {
                "model": llm_model_name,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "generation_latency_ms": round(t_gen_ms, 2)
            }

        # Structured JSON Log (no sensitive info or raw text)
        logger.info(json.dumps({
            "event": "rag_request_completed",
            "trace_id": trace_id,
            "total_latency_ms": round(t_total_ms, 2),
            "retrieved_chunks": len(selected_candidates),
            "context_chunks": len(selected_candidates),
            "citations": len(final_citations),
            "model": llm_model_name,
            "has_sufficient_context": has_sufficient_context,
            "cache_hit": cache_hit,
            "cache_stage": cache_stage
        }))

        final_response = RAGQueryResponse(
            question=request.question,
            standalone_query=standalone_query,
            answer=answer,
            citations=final_citations,
            has_sufficient_context=has_sufficient_context,
            retrieved_count=len(selected_candidates),
            latency_seconds=round(t_total_ms / 1000.0, 3),
            retrieval=retrieval_metadata,
            latency=latency_breakdown,
            trace_id=trace_id,
            trace=trace_data,
            tokens=tokens_telemetry,
            debug=debug_info if (request.debug or getattr(settings, "DEBUG", False)) else None
        )

        # Store in Answer Cache
        if ans_cache_enabled and ans_key:
            cache_manager.answer_cache.set(ans_key, final_response, tag=request.workspace_id)

        return final_response
