from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from .document import SourceType

class Citation(BaseModel):
    chunk_id: str
    document_id: str
    source_title: str
    source_type: SourceType
    file_name: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    page_index: Optional[int] = None
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    timestamp_str: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    section_title: Optional[str] = None
    snippet: str
    relevance_score: Optional[float] = None

class ChatTurn(BaseModel):
    role: str # "user" or "assistant"
    content: str

class RAGQueryRequest(BaseModel):
    question: str
    workspace_id: str = "default"
    history: List[ChatTurn] = []
    top_k: int = 5
    enable_query_rewriting: bool = True
    enable_reranking: bool = True
    document_ids: Optional[List[str]] = None
    source_types: Optional[List[SourceType]] = None
    debug: bool = False

class RAGQueryResponse(BaseModel):
    question: str
    standalone_query: str
    answer: str
    citations: List[Citation] = []
    has_sufficient_context: bool = True
    retrieved_count: int = 0
    latency_seconds: float = 0.0
    retrieval: Optional[Dict[str, Any]] = None
    latency: Optional[Dict[str, float]] = None
    debug: Optional[Dict[str, Any]] = None
