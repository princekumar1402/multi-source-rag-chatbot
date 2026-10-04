from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
import uuid

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.session import Base

if TYPE_CHECKING:
    from backend.app.models.workspace import Workspace
    from backend.app.models.document import Document

class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    document_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending, processing, completed, failed
    stage: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # validating, extracting, chunking, persisting, embedding, indexing, finalizing, completed
    progress: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="ingestion_jobs")
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="ingestion_jobs")

    __table_args__ = (
        Index("ix_ingestion_jobs_workspace_status", "workspace_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<IngestionJob(id={self.id}, status={self.status}, doc={self.document_id})>"
