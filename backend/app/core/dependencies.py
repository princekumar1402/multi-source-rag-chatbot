from typing import Optional
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.llm.base import BaseLLM
from backend.app.services.llm.groq_provider import GroqLLM
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.rag.retriever import BaseRetriever, DenseRetrieverWithReranker
from backend.app.services.rag.bm25 import BaseKeywordRetriever, BM25Retriever
from backend.app.services.rag.reranker import BaseReranker, CrossEncoderReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.context_selector import ContextSelector
from backend.app.services.rag.engine import RAGEngine
from backend.app.core.config import settings

# Global singletons for runtime efficiency
_embedder: Optional[BaseEmbedder] = None
_vector_store: Optional[BaseVectorStore] = None
_bm25_retriever: Optional[BaseKeywordRetriever] = None
_reranker: Optional[BaseReranker] = None
_retriever: Optional[BaseRetriever] = None
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

def get_bm25_retriever() -> BaseKeywordRetriever:
    global _bm25_retriever
    if _bm25_retriever is None:
        _bm25_retriever = BM25Retriever()
        # Seed BM25 with any pre-existing chunks from persistent storage
        store = get_vector_store()
        existing_chunks = store.get_all_chunks()
        if existing_chunks:
            _bm25_retriever.index_chunks(existing_chunks)
    return _bm25_retriever

def get_reranker() -> Optional[BaseReranker]:
    global _reranker
    if _reranker is None and settings.RERANKER_ENABLED:
        _reranker = CrossEncoderReranker(
            model_name=settings.RERANKER_MODEL,
            enabled=settings.RERANKER_ENABLED,
            device=settings.RERANKER_DEVICE
        )
    return _reranker

def get_retriever() -> BaseRetriever:
    global _retriever
    if _retriever is None:
        dense = DenseRetrieverWithReranker(
            embedder=get_embedder(),
            vector_store=get_vector_store(),
            min_relevance_threshold=0.0 # Thresholding handled in context selection
        )
        if settings.RETRIEVER_TYPE == "hybrid":
            bm25 = get_bm25_retriever()
            reranker = get_reranker()
            _retriever = HybridRetriever(
                dense_retriever=dense,
                keyword_retriever=bm25,
                reranker=reranker,
                dense_weight=settings.HYBRID_DENSE_WEIGHT,
                bm25_weight=settings.HYBRID_BM25_WEIGHT,
                candidate_k=settings.HYBRID_CANDIDATE_K,
                rrf_k=settings.HYBRID_RRF_K
            )
        else:
            _retriever = dense
    return _retriever

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
            vector_store=get_vector_store(),
            keyword_retriever=get_bm25_retriever()
        )
    return _pipeline

def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        context_selector = ContextSelector(
            min_relevance_score=settings.MIN_RELEVANCE_SCORE,
            max_context_chunks=settings.MAX_CONTEXT_CHUNKS,
            overlap_threshold=settings.CONTEXT_OVERLAP_THRESHOLD
        )
        _rag_engine = RAGEngine(
            retriever=get_retriever(),
            llm=get_llm(),
            context_selector=context_selector
        )
    return _rag_engine
