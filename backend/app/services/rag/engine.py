import time
from typing import List, Tuple, Dict, Any, Optional

from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse, Citation
from backend.app.schemas.document import DocumentChunk, SourceType
from backend.app.services.rag.retriever import BaseRetriever
from backend.app.services.rag.query_rewriter import ConversationalQueryRewriter
from backend.app.services.rag.prompts import SYSTEM_GROUNDED_RAG_PROMPT, USER_GROUNDED_RAG_TEMPLATE
from backend.app.services.llm.base import BaseLLM
from backend.app.core.logging import logger

class RAGEngine:
    """
    Core RAG Engine orchestrating conversational query rewriting,
    metadata-filtered retrieval, grounded generation, and citation synthesis.
    """

    def __init__(
        self,
        retriever: BaseRetriever,
        llm: BaseLLM,
        query_rewriter: Optional[ConversationalQueryRewriter] = None
    ):
        self.retriever = retriever
        self.llm = llm
        self.query_rewriter = query_rewriter or ConversationalQueryRewriter(llm=llm)

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
            elif meta.section_title:
                source_detail += f" (Section: {meta.section_title})"

            block = f"{label} {source_detail}:\n{chunk.content}"
            context_blocks.append(block)

            # Build Citation object
            citations.append(
                Citation(
                    chunk_id=chunk.chunk_id,
                    document_id=meta.document_id,
                    source_title=meta.source_name,
                    source_type=meta.source_type,
                    source_url=meta.source_url,
                    page_number=meta.page_number,
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
        start_time = time.time()
        logger.info(f"Executing RAG query: '{request.question}' in workspace: {request.workspace_id}")

        # 1. Conversational Query Rewriting
        standalone_query = request.question
        if request.enable_query_rewriting and request.history:
            standalone_query = self.query_rewriter.rewrite(request.question, request.history)

        # 2. Build metadata filters
        filters: Dict[str, Any] = {"workspace_id": request.workspace_id}
        if request.document_ids:
            filters["document_ids"] = request.document_ids

        # 3. Retrieval
        retrieved = self.retriever.retrieve(
            query=standalone_query,
            top_k=request.top_k,
            filters=filters
        )

        # Fallback if no relevant documents found
        if not retrieved:
            elapsed = time.time() - start_time
            return RAGQueryResponse(
                question=request.question,
                standalone_query=standalone_query,
                answer="The available knowledge base sources do not contain enough information to answer this question.",
                citations=[],
                has_sufficient_context=False,
                retrieved_count=0,
                latency_seconds=round(elapsed, 3)
            )

        # 4. Construct context and citations
        context_str, citations = self._build_context_and_citations(retrieved)

        # 5. Formulate Prompt
        prompt = USER_GROUNDED_RAG_TEMPLATE.format(
            context_blocks=context_str,
            question=standalone_query
        )

        # 6. LLM Generation
        try:
            answer = self.llm.generate(prompt=prompt, system_prompt=SYSTEM_GROUNDED_RAG_PROMPT)
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            elapsed = time.time() - start_time
            return RAGQueryResponse(
                question=request.question,
                standalone_query=standalone_query,
                answer=f"Error generating response: {str(e)}",
                citations=citations,
                has_sufficient_context=False,
                retrieved_count=len(retrieved),
                latency_seconds=round(elapsed, 3)
            )

        elapsed = time.time() - start_time
        insufficient_phrases = [
            "do not contain enough information",
            "does not contain enough information",
            "insufficient information"
        ]
        has_sufficient_context = not any(p in answer.lower() for p in insufficient_phrases)

        return RAGQueryResponse(
            question=request.question,
            standalone_query=standalone_query,
            answer=answer,
            citations=citations,
            has_sufficient_context=has_sufficient_context,
            retrieved_count=len(retrieved),
            latency_seconds=round(elapsed, 3)
        )
