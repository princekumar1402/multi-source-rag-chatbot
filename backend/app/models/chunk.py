from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.db.session import Base

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.workspace import Workspace

class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sheet_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    row_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp_str: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    start_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    section_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_doc_index"),
        Index("ix_chunks_workspace_doc", "workspace_id", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, doc={self.document_id}, idx={self.chunk_index})>"
