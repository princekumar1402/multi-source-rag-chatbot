from typing import Optional
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.llm.base import BaseLLM
from backend.app.services.llm.groq_provider import GroqLLM
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.services.rag.engine import RAGEngine
from backend.app.core.config import settings

# Global singletons for runtime efficiency
_embedder: Optional[BaseEmbedder] = None
_vector_store: Optional[BaseVectorStore] = None
_llm: Optional[BaseLLM] = None
_pipeline: Optional[IngestionPipeline] = None
_rag_engine: Optional[RAGEngine] = None

def get_embedder() -> BaseEmbedder:
    global _embedder
    if _embedder is None:
        _embedder = HuggingFaceEmbedder(
            model_name=settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE
        )
    return _embedder

def get_vector_store() -> BaseVectorStore:
    global _vector_store
    if _vector_store is None:
        embedder = get_embedder()
        _vector_store = FAISSVectorStore(
            dimension=embedder.dimension,
            store_dir=settings.VECTOR_STORE_PATH
        )
    return _vector_store

def get_llm() -> BaseLLM:
    global _llm
    if _llm is None:
        _llm = GroqLLM(
            api_key=settings.GROQ_API_KEY,
            model=settings.GROQ_MODEL
        )
    return _llm

def get_ingestion_pipeline() -> IngestionPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = IngestionPipeline(
            embedder=get_embedder(),
            vector_store=get_vector_store()
        )
    return _pipeline

def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        retriever = DenseRetrieverWithReranker(
            embedder=get_embedder(),
            vector_store=get_vector_store()
        )
        _rag_engine = RAGEngine(
            retriever=retriever,
            llm=get_llm()
        )
    return _rag_engine
