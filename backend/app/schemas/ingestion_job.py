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

class IngestionEventType(str, Enum):
    CURRENT_STATE = "current_state"
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_STAGE_CHANGED = "job_stage_changed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"

class IngestionEvent(BaseModel):
    event_type: str
    job_id: str
    document_id: Optional[str] = None
    workspace_id: str = "default"
    status: str
    stage: Optional[str] = None
    progress: Optional[float] = None
    error: Optional[str] = None
    source_type: Optional[str] = None
    retry_count: int = 0
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

