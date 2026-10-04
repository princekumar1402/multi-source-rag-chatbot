from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
import uuid

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.session import Base

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.chunk import Chunk
    from backend.app.models.conversation import Conversation
    from backend.app.models.ingestion_job import IngestionJob

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[List["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )


    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name})>"
