from pydantic import BaseModel, ConfigDict
from typing import Optional
from enum import Enum
from datetime import datetime

class IngestionJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class IngestionStage(str, Enum):
    VALIDATING = "validating"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    PERSISTING = "persisting"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    FINALIZING = "finalizing"
    COMPLETED = "completed"

class IngestionJobResponse(BaseModel):
    job_id: str
    document_id: Optional[str] = None
    workspace_id: str = "default"
    status: str
    stage: Optional[str] = None
    progress: Optional[float] = None
    error: Optional[str] = None
    source_type: str
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
