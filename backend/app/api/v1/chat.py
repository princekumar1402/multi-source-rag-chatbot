from fastapi import APIRouter, HTTPException, Depends
from backend.app.schemas.rag import RAGQueryRequest, RAGQueryResponse
from backend.app.core.dependencies import get_rag_engine
from backend.app.services.rag.engine import RAGEngine

router = APIRouter()

@router.post("/query", response_model=RAGQueryResponse)
def execute_rag_query(
    payload: RAGQueryRequest,
    rag_engine: RAGEngine = Depends(get_rag_engine)
) -> RAGQueryResponse:
    """
    Execute grounded RAG query over workspace documents.
    Returns strictly grounded answer, citations with timestamps/pages, and performance latency.
    """
    try:
        response = rag_engine.query(payload)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG execution failed: {str(e)}")
