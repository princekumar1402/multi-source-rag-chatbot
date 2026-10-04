from typing import List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.conversation import Conversation

class ConversationRepository:
    """Repository for Conversation persistence and querying."""

    @staticmethod
    def create(
        db: Session,
        workspace_id: str,
        title: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Conversation:
        now = datetime.now(timezone.utc)
        conv = Conversation(
            id=conversation_id or str(uuid.uuid4()),
            workspace_id=workspace_id,
            title=title or "New Conversation",
            created_at=now,
            updated_at=now
        )
        db.add(conv)
        db.flush()
        return conv

    @staticmethod
    def get(db: Session, conversation_id: str) -> Optional[Conversation]:
        return db.get(Conversation, conversation_id)

    @staticmethod
    def get_by_id_and_workspace(db: Session, conversation_id: str, workspace_id: str) -> Optional[Conversation]:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.workspace_id == workspace_id
        )
        return db.scalars(stmt).first()

    @staticmethod
    def list_by_workspace(
        db: Session,
        workspace_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[Conversation]:
        stmt = select(Conversation).where(
            Conversation.workspace_id == workspace_id
        ).order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def update_title(db: Session, conversation_id: str, title: str) -> Optional[Conversation]:
        conv = db.get(Conversation, conversation_id)
        if not conv:
            return None
        conv.title = title
        conv.updated_at = datetime.now(timezone.utc)
        db.flush()
        return conv

    @staticmethod
    def delete(db: Session, conversation_id: str) -> bool:
        conv = db.get(Conversation, conversation_id)
        if conv:
            db.delete(conv)
            db.flush()
            return True
        return False
