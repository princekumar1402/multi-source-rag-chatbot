from fastapi import APIRouter, Depends
from typing import Dict, Any
from backend.app.core.config import settings
from backend.app.core.dependencies import get_vector_store
from backend.app.services.vector_store.base import BaseVectorStore

router = APIRouter()

@router.get("/health")
def health_check(
    vector_store: BaseVectorStore = Depends(get_vector_store)
) -> Dict[str, Any]:
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": settings.GROQ_MODEL,
        "embedding_provider": settings.EMBEDDING_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_store": settings.VECTOR_STORE_TYPE,
        "indexed_chunks": vector_store.count()
    }
