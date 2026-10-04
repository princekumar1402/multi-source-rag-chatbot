from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime
import uuid

class SourceType(str, Enum):
    WEB = "web"
    YOUTUBE = "youtube"
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    CSV = "csv"
    XLSX = "xlsx"

class DocumentStatus(str, Enum):
    QUEUED = "queued"
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class ChunkMetadata(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    workspace_id: str = "default"
    source_type: SourceType
    source_name: str
    file_name: Optional[str] = None
    source_url: Optional[str] = None
    page_number: Optional[int] = None
    page_index: Optional[int] = None
    sheet_name: Optional[str] = None
    row_number: Optional[int] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    timestamp_str: Optional[str] = None
    section_title: Optional[str] = None
    chunk_index: int = 0
    token_count: Optional[int] = None

class DocumentChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: ChunkMetadata

class DocumentBase(BaseModel):
    title: str
    source_type: SourceType
    source_url: Optional[str] = None
    file_name: Optional[str] = None
    workspace_id: str = "default"
    doc_version: int = 1

class DocumentCreate(DocumentBase):
    pass

class DocumentIngestURLRequest(BaseModel):
    url: str
    workspace_id: str = "default"
    title: Optional[str] = None

class DocumentIngestYouTubeRequest(BaseModel):
    url: str
    workspace_id: str = "default"
    title: Optional[str] = None
    language: List[str] = ["en"]

class DocumentResponse(DocumentBase):
    id: str
    status: DocumentStatus
    content_hash: str
    chunk_count: int = 0
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)
