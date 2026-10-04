import os
import time
from typing import Optional
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.security import compute_content_hash
from backend.app.db.session import SessionLocal
from backend.app.models.document import Document
from backend.app.schemas.document import SourceType
from backend.app.schemas.ingestion_job import IngestionStage, IngestionEvent, IngestionEventType
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.chunk_repo import ChunkRepository
from backend.app.repositories.ingestion_job_repo import IngestionJobRepository
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.ingestion.event_bus import IngestionEventBus

def sanitize_error_message(err: Optional[str]) -> Optional[str]:
    """Sanitizes error messages to prevent exposing database credentials, tokens, or internal tracebacks."""
    if not err:
        return None
    clean = str(err)
    if "postgresql://" in clean or "password" in clean.lower():
        return "An internal database error occurred during ingestion."
    if "Traceback (most recent call last):" in clean:
        clean = clean.splitlines()[-1]
    return clean[:300]

class IngestionJobRunner:
    """
    Independent background execution runner for IngestionJobs.
    Orchestrates the entire extraction, chunking, persistence, embedding,
    and indexing lifecycle with transactional safety, rollback on failure,
    and real-time event publishing via IngestionEventBus.
    """

    def __init__(
        self,
        pipeline: IngestionPipeline,
        session_factory: Optional[sessionmaker] = None,
        event_bus: Optional[IngestionEventBus] = None
    ):
        self.pipeline = pipeline
        self.session_factory = session_factory or SessionLocal
        self.event_bus = event_bus

    def _publish_event(
        self,
        job_id: str,
        event_type: str,
        status: str,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        document_id: Optional[str] = None,
        workspace_id: str = "default",
        source_type: Optional[str] = None,
        error: Optional[str] = None,
        retry_count: int = 0
    ) -> None:
        """Publishes an event to the IngestionEventBus if configured."""
        if not self.event_bus:
            return
        try:
            event = IngestionEvent(
                event_type=event_type,
                job_id=job_id,
                document_id=document_id,
                workspace_id=workspace_id,
                status=status,
                stage=stage,
                progress=progress,
                error=sanitize_error_message(error),
                source_type=source_type,
                retry_count=retry_count
            )
            self.event_bus.publish(job_id, event)
        except Exception as e:
            logger.error(f"Failed to publish event for job {job_id}: {e}")

    def run_job(self, job_id: str, file_bytes: Optional[bytes] = None) -> None:
        """
        Executes an IngestionJob through all required lifecycle stages.
        Designed to be called by FastAPI BackgroundTasks, a worker thread, or Celery.
        """
        start_time = time.time()
        with self.session_factory() as db:
            job = IngestionJobRepository.get(db, job_id)
            if not job:
                logger.error(f"job_failed | job_id={job_id} error=Job not found in database")
                return

            doc_id = job.document_id
            doc = DocumentRepository.get(db, doc_id) if doc_id else None
            if not doc:
                logger.error(f"job_failed | job_id={job_id} error=Associated document not found")
                IngestionJobRepository.update_status(
                    db, job.id, status="failed", error_message="Associated document not found"
                )
                db.commit()
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_FAILED.value,
                    status="failed",
                    document_id=doc_id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    error="Associated document not found",
                    retry_count=job.retry_count
                )
                return

            # Concurrency Protection: check if another job is actively processing this document
            active_job = IngestionJobRepository.find_active_by_document(db, doc.id, exclude_job_id=job.id)
            if active_job and active_job.status == "processing":
                logger.warning(f"job_concurrency_collision | job_id={job.id} doc_id={doc.id} active_job={active_job.id}")
                err_msg = "Another job is actively processing this document"
                IngestionJobRepository.update_status(
                    db, job.id, status="failed", error_message=err_msg
                )
                db.commit()
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_FAILED.value,
                    status="failed",
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    error=err_msg,
                    retry_count=job.retry_count
                )
                return

            # Transition state to PROCESSING & VALIDATING
            IngestionJobRepository.update_status(
                db, job.id, status="processing", stage=IngestionStage.VALIDATING.value, progress=0.1
            )
            DocumentRepository.update_status(db, doc.id, status="processing")
            db.commit()
            logger.info(f"job_started | job_id={job.id} document_id={doc.id} source_type={job.source_type}")
            self._publish_event(
                job_id=job.id,
                event_type=IngestionEventType.JOB_STARTED.value,
                status="processing",
                stage=IngestionStage.VALIDATING.value,
                progress=0.1,
                document_id=doc.id,
                workspace_id=job.workspace_id,
                source_type=job.source_type,
                retry_count=job.retry_count
            )

            try:
                # -------------------------------------------------------------
                # 1. EXTRACTING
                # -------------------------------------------------------------
                IngestionJobRepository.update_stage(
                    db, job.id, stage=IngestionStage.EXTRACTING.value, progress=0.25
                )
                db.commit()
                logger.info(f"job_stage_changed | job_id={job.id} stage=EXTRACTING")
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
                    status="processing",
                    stage=IngestionStage.EXTRACTING.value,
                    progress=0.25,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

                if doc.source_type in (SourceType.WEB.value, SourceType.YOUTUBE.value):
                    if not doc.source_url:
                        raise ValueError(f"Document {doc.id} of type {doc.source_type} is missing source_url.")
                    loader = self.pipeline.get_loader_for_url(doc.source_url)
                    extracted = loader.load()
                else:
                    # File-based loader
                    if file_bytes is None:
                        # Attempt to load saved raw file from disk
                        os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
                        file_path = os.path.join(settings.DOCUMENTS_DIR, f"{doc.id}_{doc.file_name}")
                        if not os.path.exists(file_path):
                            file_path = os.path.join(settings.DOCUMENTS_DIR, f"{doc.id}.bin")
                        if os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                file_bytes = f.read()
                        else:
                            raise FileNotFoundError(f"Source file for document {doc.id} is not available on disk.")

                    source_type_enum = SourceType(doc.source_type)
                    loader = self.pipeline.get_loader_for_file(
                        file_bytes=file_bytes,
                        file_name=doc.file_name or "file",
                        source_type=source_type_enum
                    )
                    extracted = loader.load()

                # Preserve title if not already customized
                if not doc.title or doc.title == os.path.splitext(doc.file_name or "")[0]:
                    doc.title = extracted.title

                # -------------------------------------------------------------
                # 2. CHUNKING
                # -------------------------------------------------------------
                IngestionJobRepository.update_stage(
                    db, job.id, stage=IngestionStage.CHUNKING.value, progress=0.45
                )
                db.commit()
                logger.info(f"job_stage_changed | job_id={job.id} stage=CHUNKING")
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
                    status="processing",
                    stage=IngestionStage.CHUNKING.value,
                    progress=0.45,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

                chunks = self.pipeline.chunker.chunk_document(
                    doc=extracted,
                    document_id=doc.id,
                    workspace_id=doc.workspace_id
                )
                if not chunks:
                    raise ValueError(f"Document '{doc.title}' produced zero usable chunks.")

                # -------------------------------------------------------------
                # 3. PERSISTING (PostgreSQL Chunks)
                # -------------------------------------------------------------
                IngestionJobRepository.update_stage(
                    db, job.id, stage=IngestionStage.PERSISTING.value, progress=0.60
                )
                db.commit()
                logger.info(f"job_stage_changed | job_id={job.id} stage=PERSISTING")
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
                    status="processing",
                    stage=IngestionStage.PERSISTING.value,
                    progress=0.60,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

                # Remove any existing chunks in DB for this document (ensures idempotency on retry)
                ChunkRepository.delete_by_document(db, doc.id)

                chunks_data = [
                    {
                        "id": c.chunk_id,
                        "document_id": doc.id,
                        "workspace_id": doc.workspace_id,
                        "chunk_index": c.metadata.chunk_index,
                        "text": c.content,
                        "content_hash": compute_content_hash(c.content),
                        "source_type": c.metadata.source_type.value if hasattr(c.metadata.source_type, "value") else str(c.metadata.source_type),
                        "source_name": c.metadata.source_name,
                        "file_name": c.metadata.file_name,
                        "source_url": c.metadata.source_url,
                        "page_number": c.metadata.page_number,
                        "page_index": c.metadata.page_index,
                        "sheet_name": c.metadata.sheet_name,
                        "row_number": c.metadata.row_number,
                        "timestamp_str": c.metadata.timestamp_str,
                        "start_time": c.metadata.start_time,
                        "end_time": c.metadata.end_time,
                        "section_title": c.metadata.section_title,
                        "token_count": c.metadata.token_count
                    }
                    for c in chunks
                ]
                ChunkRepository.create_many(db, chunks_data)
                db.flush()

                # -------------------------------------------------------------
                # 4. EMBEDDING
                # -------------------------------------------------------------
                IngestionJobRepository.update_stage(
                    db, job.id, stage=IngestionStage.EMBEDDING.value, progress=0.75
                )
                db.commit()
                logger.info(f"job_stage_changed | job_id={job.id} stage=EMBEDDING")
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
                    status="processing",
                    stage=IngestionStage.EMBEDDING.value,
                    progress=0.75,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

                chunk_texts = [c.content for c in chunks]
                embeddings = self.pipeline.embedder.embed_documents(chunk_texts)

                # -------------------------------------------------------------
                # 5. INDEXING (FAISS & BM25)
                # -------------------------------------------------------------
                IngestionJobRepository.update_stage(
                    db, job.id, stage=IngestionStage.INDEXING.value, progress=0.90
                )
                db.commit()
                logger.info(f"job_stage_changed | job_id={job.id} stage=INDEXING")
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
                    status="processing",
                    stage=IngestionStage.INDEXING.value,
                    progress=0.90,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

                # Purge old vectors/tokens from memory & disk before adding (idempotent retry)
                self.pipeline.vector_store.delete_document(doc.id)
                if self.pipeline.keyword_retriever:
                    self.pipeline.keyword_retriever.remove_document(doc.id)

                self.pipeline.vector_store.add_chunks(chunks=chunks, embeddings=embeddings)
                if self.pipeline.keyword_retriever:
                    self.pipeline.keyword_retriever.index_chunks(chunks)

                # -------------------------------------------------------------
                # 6. FINALIZING & CONSISTENCY CHECK
                # -------------------------------------------------------------
                IngestionJobRepository.update_stage(
                    db, job.id, stage=IngestionStage.FINALIZING.value, progress=0.95
                )
                db.commit()
                logger.info(f"job_stage_changed | job_id={job.id} stage=FINALIZING")
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
                    status="processing",
                    stage=IngestionStage.FINALIZING.value,
                    progress=0.95,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

                # Verify consistency between DB chunks and expected chunk count
                persisted_chunks = ChunkRepository.list_by_document(db, doc.id)
                if len(persisted_chunks) != len(chunks):
                    raise RuntimeError(
                        f"Consistency verification failed: {len(persisted_chunks)} chunks in DB, "
                        f"expected {len(chunks)}."
                    )

                # Merge document metadata
                merged_meta = dict(doc.doc_metadata or {})
                if extracted.metadata:
                    merged_meta.update(extracted.metadata)

                # Mark document READY and job COMPLETED
                DocumentRepository.update_status(
                    db,
                    doc.id,
                    status="ready",
                    chunk_count=len(chunks),
                    title=extracted.title,
                    metadata=merged_meta
                )
                IngestionJobRepository.update_status(
                    db,
                    job.id,
                    status="completed",
                    stage=IngestionStage.COMPLETED.value,
                    progress=1.0
                )
                db.commit()

                duration = time.time() - start_time
                logger.info(
                    f"job_completed | job_id={job.id} document_id={doc.id} "
                    f"chunks={len(chunks)} duration={duration:.2f}s"
                )
                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_COMPLETED.value,
                    status="completed",
                    stage=IngestionStage.COMPLETED.value,
                    progress=1.0,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    retry_count=job.retry_count
                )

            except Exception as e:
                duration = time.time() - start_time
                err_msg = str(e)
                logger.error(
                    f"job_failed | job_id={job.id} document_id={doc.id} "
                    f"stage={job.stage} error={err_msg} duration={duration:.2f}s"
                )

                # Rollback partial index state
                try:
                    self.pipeline.vector_store.delete_document(doc.id)
                except Exception as ve:
                    logger.error(f"Error purging FAISS vectors during rollback: {ve}")

                try:
                    if self.pipeline.keyword_retriever:
                        self.pipeline.keyword_retriever.remove_document(doc.id)
                except Exception as ke:
                    logger.error(f"Error purging BM25 tokens during rollback: {ke}")

                # Delete partially created chunks in PostgreSQL
                try:
                    ChunkRepository.delete_by_document(db, doc.id)
                except Exception as ce:
                    logger.error(f"Error purging DB chunks during rollback: {ce}")

                # Mark document FAILED and job FAILED
                DocumentRepository.update_status(
                    db,
                    doc.id,
                    status="failed",
                    error_message=err_msg
                )
                IngestionJobRepository.update_status(
                    db,
                    job.id,
                    status="failed",
                    error_message=err_msg
                )
                db.commit()

                self._publish_event(
                    job_id=job.id,
                    event_type=IngestionEventType.JOB_FAILED.value,
                    status="failed",
                    stage=job.stage,
                    progress=job.progress,
                    document_id=doc.id,
                    workspace_id=job.workspace_id,
                    source_type=job.source_type,
                    error=err_msg,
                    retry_count=job.retry_count
                )
