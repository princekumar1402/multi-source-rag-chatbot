from typing import List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.workspace import Workspace

class WorkspaceRepository:
    """Repository for Workspace database operations."""

    @staticmethod
    def create(
        db: Session,
        name: str,
        description: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> Workspace:
        ws = Workspace(
            id=workspace_id or str(uuid.uuid4()),
            name=name,
            description=description,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(ws)
        db.flush()
        return ws

    @staticmethod
    def get(db: Session, workspace_id: str) -> Optional[Workspace]:
        return db.get(Workspace, workspace_id)

    @staticmethod
    def get_or_create(
        db: Session,
        workspace_id: str = "default",
        name: Optional[str] = None
    ) -> Workspace:
        ws = db.get(Workspace, workspace_id)
        if not ws:
            ws = Workspace(
                id=workspace_id,
                name=name or f"Workspace {workspace_id}",
                description="Default workspace" if workspace_id == "default" else None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.add(ws)
            db.flush()
        return ws

    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100) -> List[Workspace]:
        stmt = select(Workspace).order_by(Workspace.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def delete(db: Session, workspace_id: str) -> bool:
        ws = db.get(Workspace, workspace_id)
        if ws:
            db.delete(ws)
            db.flush()
            return True
        return False
