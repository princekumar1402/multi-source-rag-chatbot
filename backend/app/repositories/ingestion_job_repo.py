from typing import List, Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.app.models.ingestion_job import IngestionJob

class IngestionJobRepository:
    """Repository for IngestionJob audit trail and status tracking."""

    @staticmethod
    def create(
        db: Session,
        workspace_id: str,
        source_type: str,
        document_id: Optional[str] = None,
        status: str = "pending",
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        job_id: Optional[str] = None
    ) -> IngestionJob:
        now = datetime.now(timezone.utc)
        job = IngestionJob(
            id=job_id or str(uuid.uuid4()),
            workspace_id=workspace_id,
            document_id=document_id,
            status=status,
            stage=stage,
            progress=progress,
            source_type=source_type,
            started_at=now if status == "processing" else None,
            completed_at=None,
            retry_count=0,
            created_at=now
        )
        db.add(job)
        db.flush()
        return job

    @staticmethod
    def get(db: Session, job_id: str) -> Optional[IngestionJob]:
        return db.get(IngestionJob, job_id)

    @staticmethod
    def get_by_id_and_workspace(db: Session, job_id: str, workspace_id: str) -> Optional[IngestionJob]:
        stmt = select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.workspace_id == workspace_id
        )
        return db.scalars(stmt).first()

    @staticmethod
    def find_active_by_document(db: Session, document_id: str, exclude_job_id: Optional[str] = None) -> Optional[IngestionJob]:
        """Finds any currently running (pending or processing) job for a document."""
        stmt = select(IngestionJob).where(
            IngestionJob.document_id == document_id,
            IngestionJob.status.in_(["pending", "processing"])
        )
        if exclude_job_id:
            stmt = stmt.where(IngestionJob.id != exclude_job_id)
        return db.scalars(stmt).first()

    @staticmethod
    def list_by_workspace(
        db: Session,
        workspace_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[IngestionJob]:
        stmt = select(IngestionJob).where(IngestionJob.workspace_id == workspace_id)
        if status:
            stmt = stmt.where(IngestionJob.status == status)
        stmt = stmt.order_by(IngestionJob.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def update_status(
        db: Session,
        job_id: str,
        status: str,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> Optional[IngestionJob]:
        job = db.get(IngestionJob, job_id)
        if not job:
            return None
        job.status = status
        now = datetime.now(timezone.utc)
        if status == "processing" and not job.started_at:
            job.started_at = now
        elif status in ("completed", "failed", "cancelled"):
            job.completed_at = now
        if stage is not None:
            job.stage = stage
        if progress is not None:
            job.progress = progress
        if error_message is not None:
            job.error_message = error_message
        db.flush()
        return job

    @staticmethod
    def update_stage(
        db: Session,
        job_id: str,
        stage: str,
        progress: Optional[float] = None
    ) -> Optional[IngestionJob]:
        job = db.get(IngestionJob, job_id)
        if not job:
            return None
        job.stage = stage
        if progress is not None:
            job.progress = progress
        db.flush()
        return job

    @staticmethod
    def reset_for_retry(db: Session, job_id: str) -> Optional[IngestionJob]:
        """Resets a failed job to pending state for safe retry."""
        job = db.get(IngestionJob, job_id)
        if not job:
            return None
        job.status = "pending"
        job.stage = None
        job.progress = 0.0
        job.error_message = None
        job.started_at = None
        job.completed_at = None
        job.retry_count += 1
        db.flush()
        return job
