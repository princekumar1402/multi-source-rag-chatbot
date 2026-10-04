from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.documents import router as documents_router
from backend.app.api.v1.chat import router as chat_router
from backend.app.api.v1.workspaces import router as workspaces_router
from backend.app.api.v1.conversations import router as conversations_router

from backend.app.api.v1.ingestion import router as ingestion_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, prefix="", tags=["Health"])
api_v1_router.include_router(documents_router, prefix="/documents", tags=["Documents"])
api_v1_router.include_router(ingestion_router, prefix="/ingestion", tags=["Ingestion Jobs"])
api_v1_router.include_router(chat_router, prefix="/chat", tags=["Chat & RAG"])
api_v1_router.include_router(workspaces_router, prefix="/workspaces", tags=["Workspaces"])
api_v1_router.include_router(conversations_router, prefix="/conversations", tags=["Conversations"])
