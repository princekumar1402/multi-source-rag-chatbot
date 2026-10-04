from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    workspace_id: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
