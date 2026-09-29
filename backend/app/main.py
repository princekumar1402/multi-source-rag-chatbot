from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.api.v1.router import api_v1_router
from backend.app.core.dependencies import get_embedder, get_vector_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Multi-Source RAG Platform Backend...")
    # Pre-warm embedder and vector store
    get_embedder()
    get_vector_store()
    logger.info("RAG Platform backend initialized successfully.")
    yield
    logger.info("Shutting down RAG Platform backend...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Production-grade Multi-Source RAG Platform with Grounded Answers and Citations",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {
        "project": settings.PROJECT_NAME,
        "docs": "/docs",
        "api_v1": settings.API_V1_STR
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
