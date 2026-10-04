from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from sqlalchemy.orm import Session

from backend.app.schemas.workspace import WorkspaceCreate, WorkspaceResponse
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.db.session import get_db

router = APIRouter()

@router.get("", response_model=List[WorkspaceResponse])
def list_workspaces(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
) -> List[WorkspaceResponse]:
    """List all workspaces."""
    # Ensure default workspace is seeded
    WorkspaceRepository.get_or_create(db, workspace_id="default")
    db.commit()
    workspaces = WorkspaceRepository.list(db, skip=skip, limit=limit)
    return [WorkspaceResponse.model_validate(ws) for ws in workspaces]

@router.post("", response_model=WorkspaceResponse, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db)
) -> WorkspaceResponse:
    """Create a new workspace."""
    if payload.workspace_id:
        existing = WorkspaceRepository.get(db, payload.workspace_id)
        if existing:
            raise HTTPException(status_code=400, detail=f"Workspace '{payload.workspace_id}' already exists")

    ws = WorkspaceRepository.create(
        db=db,
        name=payload.name,
        description=payload.description,
        workspace_id=payload.workspace_id
    )
    db.commit()
    return WorkspaceResponse.model_validate(ws)

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(
    workspace_id: str,
    db: Session = Depends(get_db)
) -> WorkspaceResponse:
    """Get workspace details by ID."""
    ws = WorkspaceRepository.get(db, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(ws)
