from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.document import Document

class DocumentRepository:
    """Repository for Document persistence and querying."""

    @staticmethod
    def create(
        db: Session,
        workspace_id: str,
        source_type: str,
        title: str,
        content_hash: str,
        document_id: Optional[str] = None,
        file_name: Optional[str] = None,
        source_url: Optional[str] = None,
        status: str = "pending",
        size_bytes: Optional[int] = None,
        doc_metadata: Optional[Dict[str, Any]] = None
    ) -> Document:
        now = datetime.now(timezone.utc)
        doc = Document(
            id=document_id or str(uuid.uuid4()),
            workspace_id=workspace_id,
            source_type=source_type,
            title=title,
            file_name=file_name,
            source_url=source_url,
            content_hash=content_hash,
            status=status,
            size_bytes=size_bytes,
            chunk_count=0,
            doc_metadata=doc_metadata or {},
            created_at=now,
            updated_at=now
        )
        db.add(doc)
        db.flush()
        return doc

    @staticmethod
    def get(db: Session, document_id: str) -> Optional[Document]:
        return db.get(Document, document_id)

    @staticmethod
    def get_by_id_and_workspace(db: Session, document_id: str, workspace_id: str) -> Optional[Document]:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id
        )
        return db.scalars(stmt).first()

    @staticmethod
    def list_by_workspace(
        db: Session,
        workspace_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Document]:
        stmt = select(Document).where(Document.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(Document.status == status)
        stmt = stmt.order_by(Document.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def find_by_hash(db: Session, workspace_id: str, content_hash: str) -> Optional[Document]:
        stmt = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.content_hash == content_hash
        )
        return db.scalars(stmt).first()

    @staticmethod
    def find_by_url(db: Session, workspace_id: str, source_url: str) -> Optional[Document]:
        stmt = select(Document).where(
            Document.workspace_id == workspace_id,
            Document.source_url == source_url
        )
        return db.scalars(stmt).first()

    @staticmethod
    def update_status(
        db: Session,
        document_id: str,
        status: str,
        chunk_count: Optional[int] = None,
        error_message: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Document]:
        doc = db.get(Document, document_id)
        if not doc:
            return None
        doc.status = status
        doc.updated_at = datetime.now(timezone.utc)
        if chunk_count is not None:
            doc.chunk_count = chunk_count
        if error_message is not None:
            doc.error_message = error_message
        if title is not None:
            doc.title = title
        if metadata is not None:
            current = dict(doc.doc_metadata)
            current.update(metadata)
            doc.doc_metadata = current
        db.flush()
        return doc

    @staticmethod
    def delete(db: Session, document_id: str) -> bool:
        doc = db.get(Document, document_id)
        if doc:
            db.delete(doc)
            db.flush()
            return True
        return False
