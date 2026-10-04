from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.app.models.chunk import Chunk

class ChunkRepository:
    """Repository for Chunk persistence, bulk insertion, and querying."""

    @staticmethod
    def create_many(db: Session, chunks_data: List[Dict[str, Any]]) -> List[Chunk]:
        now = datetime.now(timezone.utc)
        chunk_objects = []
        for item in chunks_data:
            chunk = Chunk(
                id=item["id"],
                document_id=item["document_id"],
                workspace_id=item["workspace_id"],
                chunk_index=item["chunk_index"],
                text=item["text"],
                content_hash=item.get("content_hash"),
                source_type=item["source_type"],
                source_name=item["source_name"],
                file_name=item.get("file_name"),
                source_url=item.get("source_url"),
                page_number=item.get("page_number"),
                page_index=item.get("page_index"),
                sheet_name=item.get("sheet_name"),
                row_number=item.get("row_number"),
                timestamp_str=item.get("timestamp_str"),
                start_time=item.get("start_time"),
                end_time=item.get("end_time"),
                section_title=item.get("section_title"),
                token_count=item.get("token_count"),
                created_at=now
            )
            chunk_objects.append(chunk)

        db.add_all(chunk_objects)
        db.flush()
        return chunk_objects

    @staticmethod
    def list_by_document(db: Session, document_id: str) -> List[Chunk]:
        stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index.asc())
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_by_workspace(
        db: Session,
        workspace_id: str,
        skip: int = 0,
        limit: int = 500
    ) -> List[Chunk]:
        stmt = select(Chunk).where(Chunk.workspace_id == workspace_id).order_by(Chunk.created_at.asc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def get(db: Session, chunk_id: str) -> Optional[Chunk]:
        return db.get(Chunk, chunk_id)

    @staticmethod
    def delete_by_document(db: Session, document_id: str) -> int:
        stmt = delete(Chunk).where(Chunk.document_id == document_id)
        result = db.execute(stmt)
        db.flush()
        return result.rowcount
