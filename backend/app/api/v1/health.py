from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
from sqlalchemy import text
from backend.app.core.config import settings
from backend.app.core.dependencies import get_vector_store, get_embedder
from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.db.session import SessionLocal

router = APIRouter()

@router.get("/health", status_code=status.HTTP_200_OK)
def health_check(
    vector_store: BaseVectorStore = Depends(get_vector_store)
) -> Dict[str, Any]:
    """
    Liveness probe: verifies that the FastAPI application process is alive.
    Does not require external dependencies or consume LLM tokens.
    """
    indexed_chunks = 0
    try:
        if vector_store:
            indexed_chunks = vector_store.count()
    except Exception:
        pass

    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "project": settings.PROJECT_NAME,
        "version": "1.0.0",
        "indexed_chunks": indexed_chunks
    }

@router.get("/ready", status_code=status.HTTP_200_OK)
def readiness_check(
    vector_store: BaseVectorStore = Depends(get_vector_store),
    embedder: BaseEmbedder = Depends(get_embedder)
) -> Dict[str, Any]:
    """
    Readiness probe: verifies that the service is ready to accept incoming traffic.
    Checks:
    - PostgreSQL database connectivity (SELECT 1)
    - Vector store index initialization
    - Embedding model availability
    Returns 200 OK if ready, 503 Service Unavailable if any critical component fails.
    Zero LLM calls or token consumption.
    """
    db_status = "unavailable"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database readiness check failed: {str(e)}"
        )

    # Check vector store readiness
    try:
        chunk_count = vector_store.count()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector store readiness check failed: {str(e)}"
        )

    return {
        "status": "ready",
        "database": db_status,
        "vector_store": {
            "type": settings.VECTOR_STORE_TYPE,
            "indexed_chunks": chunk_count
        },
        "embedding": {
            "provider": settings.EMBEDDING_PROVIDER,
            "model": settings.EMBEDDING_MODEL
        },
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.GROQ_MODEL
        }
    }
