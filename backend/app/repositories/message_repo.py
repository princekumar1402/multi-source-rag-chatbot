from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.message import Message

class MessageRepository:
    """Repository for Message persistence and querying."""

    @staticmethod
    def create(
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        msg_metadata: Optional[Dict[str, Any]] = None,
        message_id: Optional[str] = None
    ) -> Message:
        msg = Message(
            id=message_id or str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            msg_metadata=msg_metadata or {},
            created_at=datetime.now(timezone.utc)
        )
        db.add(msg)
        db.flush()
        return msg

    @staticmethod
    def list_by_conversation(
        db: Session,
        conversation_id: str,
        limit: int = 50
    ) -> List[Message]:
        stmt = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).limit(limit)
        return list(db.scalars(stmt).all())
