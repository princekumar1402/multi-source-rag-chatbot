from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
import uuid

from sqlalchemy import String, Text, BigInteger, Integer, DateTime, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.session import Base

if TYPE_CHECKING:
    from backend.app.models.workspace import Workspace
    from backend.app.models.chunk import Chunk
    from backend.app.models.ingestion_job import IngestionJob

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

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
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="documents")
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[List["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="document",
        cascade="all, delete-orphan"
    )


    __table_args__ = (


        UniqueConstraint("workspace_id", "content_hash", name="uq_document_workspace_hash"),
        Index("ix_documents_workspace_status", "workspace_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, title={self.title}, status={self.status})>"
