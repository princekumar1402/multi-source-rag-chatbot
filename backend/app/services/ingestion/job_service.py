import os
import uuid
from typing import Optional, Tuple
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.security import compute_file_hash, normalize_url
from backend.app.db.session import SessionLocal
from backend.app.schemas.document import SourceType, DocumentStatus
from backend.app.schemas.ingestion_job import IngestionJobResponse, IngestionJobStatus, IngestionStage
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.ingestion_job_repo import IngestionJobRepository
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.ingestion.job_runner import IngestionJobRunner
from backend.app.services.ingestion.youtube.service import YouTubeIngestionService

class IngestionJobService:
    """
    Domain service for orchestrating ingestion job creation, status querying,
    and retry management. Completely decoupled from FastAPI HTTP request lifecycles.
    """

    def __init__(
        self,
        pipeline: IngestionPipeline,
        runner: Optional[IngestionJobRunner] = None,
        session_factory: Optional[sessionmaker] = None
    ):
        self.pipeline = pipeline
        self.session_factory = session_factory or SessionLocal
        self.runner = runner or IngestionJobRunner(pipeline=pipeline, session_factory=self.session_factory)

    def _job_to_response(self, job) -> IngestionJobResponse:
        return IngestionJobResponse(
            job_id=job.id,
            document_id=job.document_id,
            workspace_id=job.workspace_id,
            status=job.status,
            stage=job.stage,
            progress=job.progress,
            error=job.error_message,
            source_type=job.source_type,
            retry_count=job.retry_count,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at
        )

    def create_file_job(
        self,
        file_bytes: bytes,
        file_name: str,
        workspace_id: str = "default",
        custom_title: Optional[str] = None
    ) -> Tuple[IngestionJobResponse, bool]:
        """
        Validates file, checks SHA-256 deduplication, creates Document & IngestionJob,
        persists raw file for durability/retry, and commits.
        Returns (IngestionJobResponse, needs_processing: bool).
        """
        # 1. Validate file format and size
        source_type = self.pipeline.validate_file(file_bytes, file_name)

        # 2. SHA-256 deduplication
        file_hash = compute_file_hash(file_bytes)

        with self.session_factory() as db:
            WorkspaceRepository.get_or_create(db, workspace_id=workspace_id)

            existing = DocumentRepository.find_by_hash(db, workspace_id=workspace_id, content_hash=file_hash)
            if existing and existing.status == DocumentStatus.READY.value:
                logger.info(f"Duplicate document detected (ready): {existing.id} ('{existing.title}')")
                # Look for an existing completed job or create an instant completed job record
                existing_jobs = IngestionJobRepository.list_by_workspace(db, workspace_id=workspace_id, limit=50)
                matching_job = next((j for j in existing_jobs if j.document_id == existing.id and j.status == "completed"), None)
                if not matching_job:
                    matching_job = IngestionJobRepository.create(
                        db=db,
                        workspace_id=workspace_id,
                        source_type=source_type.value,
                        document_id=existing.id,
                        status="completed",
                        stage=IngestionStage.COMPLETED.value,
                        progress=1.0
                    )
                    db.commit()
                return self._job_to_response(matching_job), False

            # If existing document is FAILED, we reuse/reset it
            if existing and existing.status == DocumentStatus.FAILED.value:
                doc_id = existing.id
                doc_title = custom_title or existing.title
                DocumentRepository.update_status(db, doc_id, status="pending", error_message=None, title=doc_title)
            else:
                doc_id = str(uuid.uuid4())
                doc_title = custom_title or os.path.splitext(file_name)[0]
                DocumentRepository.create(
                    db=db,
                    workspace_id=workspace_id,
                    source_type=source_type.value,
                    title=doc_title,
                    content_hash=file_hash,
                    document_id=doc_id,
                    file_name=file_name,
                    status="pending",
                    size_bytes=len(file_bytes),
                    doc_metadata={"file_name": file_name, "file_size_bytes": len(file_bytes)}
                )

            # Persist raw file for durability & retry support
            os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
            stored_file_path = os.path.join(settings.DOCUMENTS_DIR, f"{doc_id}_{file_name}")
            with open(stored_file_path, "wb") as f:
                f.write(file_bytes)

            # Create IngestionJob in PENDING state
            job = IngestionJobRepository.create(
                db=db,
                workspace_id=workspace_id,
                source_type=source_type.value,
                document_id=doc_id,
                status="pending",
                stage=IngestionStage.VALIDATING.value,
                progress=0.05
            )
            db.commit()
            logger.info(f"job_created | job_id={job.id} document_id={doc_id} source_type={source_type.value}")
            return self._job_to_response(job), True

    def create_url_job(
        self,
        url: str,
        workspace_id: str = "default",
        custom_title: Optional[str] = None,
        is_youtube: bool = False
    ) -> Tuple[IngestionJobResponse, bool]:
        """
        Validates URL/YouTube, checks deduplication, creates Document & IngestionJob, and commits.
        Returns (IngestionJobResponse, needs_processing: bool).
        """
        url_clean = url.strip()
        if not url_clean:
            raise ValueError("URL cannot be empty.")

        if is_youtube:
            # Validates YouTube URL syntax and video ID
            YouTubeIngestionService().extract_video_id(url_clean)
            source_type = SourceType.YOUTUBE.value
        else:
            source_type = SourceType.WEB.value

        norm_url = normalize_url(url_clean)

        with self.session_factory() as db:
            WorkspaceRepository.get_or_create(db, workspace_id=workspace_id)

            existing = DocumentRepository.find_by_url(db, workspace_id=workspace_id, source_url=norm_url)
            if existing and existing.status == DocumentStatus.READY.value:
                logger.info(f"Duplicate URL document detected (ready): {existing.id} ('{existing.title}')")
                existing_jobs = IngestionJobRepository.list_by_workspace(db, workspace_id=workspace_id, limit=50)
                matching_job = next((j for j in existing_jobs if j.document_id == existing.id and j.status == "completed"), None)
                if not matching_job:
                    matching_job = IngestionJobRepository.create(
                        db=db,
                        workspace_id=workspace_id,
                        source_type=source_type,
                        document_id=existing.id,
                        status="completed",
                        stage=IngestionStage.COMPLETED.value,
                        progress=1.0
                    )
                    db.commit()
                return self._job_to_response(matching_job), False

            # If existing document is FAILED, reuse/reset it
            if existing and existing.status == DocumentStatus.FAILED.value:
                doc_id = existing.id
                doc_title = custom_title or existing.title
                DocumentRepository.update_status(db, doc_id, status="pending", error_message=None, title=doc_title)
            else:
                doc_id = str(uuid.uuid4())
                doc_title = custom_title or (f"YouTube Video" if is_youtube else f"Webpage: {url_clean[:40]}")
                # Generate a temporary unique content hash based on URL until content is extracted
                content_hash = f"url_hash_{uuid.uuid4().hex}"
                DocumentRepository.create(
                    db=db,
                    workspace_id=workspace_id,
                    source_type=source_type,
                    title=doc_title,
                    content_hash=content_hash,
                    document_id=doc_id,
                    source_url=norm_url,
                    status="pending",
                    doc_metadata={"source_url": norm_url}
                )

            # Create IngestionJob in PENDING state
            job = IngestionJobRepository.create(
                db=db,
                workspace_id=workspace_id,
                source_type=source_type,
                document_id=doc_id,
                status="pending",
                stage=IngestionStage.VALIDATING.value,
                progress=0.05
            )
            db.commit()
            logger.info(f"job_created | job_id={job.id} document_id={doc_id} source_type={source_type}")
            return self._job_to_response(job), True

    def get_job_status(self, job_id: str, workspace_id: Optional[str] = None) -> Optional[IngestionJobResponse]:
        """Fetches the current status and stage of an IngestionJob."""
        with self.session_factory() as db:
            if workspace_id:
                job = IngestionJobRepository.get_by_id_and_workspace(db, job_id, workspace_id)
            else:
                job = IngestionJobRepository.get(db, job_id)
            if not job:
                return None
            return self._job_to_response(job)

    def retry_job(self, job_id: str, workspace_id: Optional[str] = None) -> Tuple[IngestionJobResponse, bool]:
        """
        Safely retries a FAILED ingestion job.
        Ensures idempotency, resets job/document status, and prepares for execution.
        """
        with self.session_factory() as db:
            if workspace_id:
                job = IngestionJobRepository.get_by_id_and_workspace(db, job_id, workspace_id)
            else:
                job = IngestionJobRepository.get(db, job_id)

            if not job:
                raise ValueError(f"Job '{job_id}' not found.")

            if job.status != IngestionJobStatus.FAILED.value:
                raise ValueError(
                    f"Job '{job_id}' is currently '{job.status}'. Only FAILED jobs can be retried."
                )

            # Ensure no other active job is already processing the same document
            if job.document_id:
                active_job = IngestionJobRepository.find_active_by_document(db, job.document_id, exclude_job_id=job.id)
                if active_job and active_job.status in ("pending", "processing"):
                    raise ValueError(
                        f"Cannot retry: Another job ({active_job.id}) is actively processing document {job.document_id}."
                    )

                # Reset document status to pending
                DocumentRepository.update_status(db, job.document_id, status="pending", error_message=None)

            # Reset job for retry
            updated_job = IngestionJobRepository.reset_for_retry(db, job.id)
            db.commit()
            logger.info(f"job_retry_started | job_id={job.id} document_id={job.document_id} attempt={updated_job.retry_count}")
            return self._job_to_response(updated_job), True
