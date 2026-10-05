from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Multi-Source RAG Platform"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Security
    ALLOWED_HOSTS: List[str] = ["*"]
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8501"
    ]

    # Database Settings (PostgreSQL / SQLite fallback)
    DATABASE_URL: str = "postgresql://rag_user:rag_password@localhost:5434/rag_db"

    # LLM Settings
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    LLM_TEMPERATURE: float = 0.0


    # Embeddings Settings
    EMBEDDING_PROVIDER: str = "huggingface"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # Vector Store Settings
    VECTOR_STORE_TYPE: str = "faiss"
    VECTOR_STORE_PATH: str = "data/vector_store"

    # Ingestion & Chunking
    DEFAULT_CHUNK_SIZE: int = 1000
    DEFAULT_CHUNK_OVERLAP: int = 200
    MAX_FILE_SIZE_MB: int = 25

    # YouTube Ingestion Settings
    YOUTUBE_TRANSCRIPT_PROVIDER: str = "auto" # "auto", "youtube_transcript_api", "ytdlp", "whisper"
    YOUTUBE_LANGUAGES: List[str] = ["en"]
    YOUTUBE_ASR_ENABLED: bool = False
    YOUTUBE_ASR_MODEL: str = "tiny"
    YOUTUBE_MAX_DURATION_SECONDS: int = 1800 # 30 minutes
    YOUTUBE_MAX_AUDIO_SIZE_MB: int = 50

    # Storage Paths
    DATA_DIR: str = "data"
    DOCUMENTS_DIR: str = "data/documents"

    # Retrieval & Hybrid Search
    RETRIEVER_TYPE: str = "hybrid" # "hybrid" or "dense"
    HYBRID_DENSE_WEIGHT: float = 0.5
    HYBRID_BM25_WEIGHT: float = 0.5
    HYBRID_CANDIDATE_K: int = 20
    HYBRID_RRF_K: int = 60

    # Reranker Settings
    RERANKER_ENABLED: bool = True
    RERANKER_PROVIDER: str = "cross-encoder"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_DEVICE: str = "cpu"

    # Context Selection & Grounding
    MAX_CONTEXT_CHUNKS: int = 6
    MIN_RELEVANCE_SCORE: float = 0.15
    CONTEXT_OVERLAP_THRESHOLD: float = 0.85

    # Phase 10 - Caching & Optimization Settings
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    CACHE_MAX_SIZE: int = 1000
    EMBEDDING_CACHE_ENABLED: bool = True
    RETRIEVAL_CACHE_ENABLED: bool = True
    ANSWER_CACHE_ENABLED: bool = True
    QUERY_REWRITE_CACHE_ENABLED: bool = True
    RERANKER_CACHE_ENABLED: bool = True

    # Phase 10 - Database Connection Pooling Settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Phase 10 - Performance Benchmarking
    PERFORMANCE_BENCHMARK_ENABLED: bool = False

    model_config = SettingsConfigDict(
        env_file=(
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env")),
            ".env",
            "backend/.env"
        ),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# Ensure required directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
os.makedirs(settings.VECTOR_STORE_PATH, exist_ok=True)
