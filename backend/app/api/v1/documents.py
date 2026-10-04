import os
import glob
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form, BackgroundTasks
from typing import List, Optional

from backend.app.schemas.document import (
    DocumentResponse,
    DocumentIngestURLRequest,
    DocumentIngestYouTubeRequest,
    DocumentStatus
)
from backend.app.schemas.ingestion_job import IngestionJobResponse
from backend.app.core.config import settings
from backend.app.core.dependencies import get_ingestion_pipeline, get_ingestion_job_service
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.ingestion.job_service import IngestionJobService
from backend.app.services.ingestion.youtube.exceptions import YouTubeIngestionError

router = APIRouter()

@router.post("/upload", response_model=IngestionJobResponse, status_code=202)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace_id: str = Form("default"),
    title: Optional[str] = Form(None),
    job_service: IngestionJobService = Depends(get_ingestion_job_service)
) -> IngestionJobResponse:
    """
    Asynchronously upload and ingest a document file (.pdf, .docx, .txt, .md, .csv, .xlsx).
    Validates file format, detects duplicates via SHA-256, initializes Document & IngestionJob,
    and returns immediately with job_id while extraction/indexing runs in the background.
    """
    try:
        file_bytes = await file.read()
        file_name = file.filename or "uploaded_file"
        job_resp, needs_processing = job_service.create_file_job(
            file_bytes=file_bytes,
            file_name=file_name,
            workspace_id=workspace_id,
            custom_title=title
        )
        if needs_processing:
            background_tasks.add_task(
                job_service.runner.run_job,
                job_id=job_resp.job_id,
                file_bytes=file_bytes
            )
        return job_resp
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal file ingestion error: {str(e)}")

@router.post("/url", response_model=IngestionJobResponse, status_code=202)
def ingest_web_url(
    payload: DocumentIngestURLRequest,
    background_tasks: BackgroundTasks,
    job_service: IngestionJobService = Depends(get_ingestion_job_service)
) -> IngestionJobResponse:
    """
    Asynchronously ingest, clean, chunk, embed, and index a webpage or article URL.
    Returns immediately with job_id for background status tracking.
    """
    try:
        job_resp, needs_processing = job_service.create_url_job(
            url=payload.url,
            workspace_id=payload.workspace_id,
            custom_title=payload.title,
            is_youtube=False
        )
        if needs_processing:
            background_tasks.add_task(
                job_service.runner.run_job,
                job_id=job_resp.job_id
            )
        return job_resp
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal ingestion error: {str(e)}")

@router.post("/youtube", response_model=IngestionJobResponse, status_code=202)
def ingest_youtube_url(
    payload: DocumentIngestYouTubeRequest,
    background_tasks: BackgroundTasks,
    job_service: IngestionJobService = Depends(get_ingestion_job_service)
) -> IngestionJobResponse:
    """
    Asynchronously ingest, extract transcript, chunk, embed, and index a YouTube video.
    Returns immediately with job_id for background status tracking.
    """
    try:
        job_resp, needs_processing = job_service.create_url_job(
            url=payload.url,
            workspace_id=payload.workspace_id,
            custom_title=payload.title,
            is_youtube=True
        )
        if needs_processing:
            background_tasks.add_task(
                job_service.runner.run_job,
                job_id=job_resp.job_id
            )
        return job_resp
    except (YouTubeIngestionError, ValueError) as yte:
        raise HTTPException(status_code=400, detail=str(yte))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal YouTube ingestion error: {str(e)}")

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    workspace_id: str = Query("default", description="Workspace ID to filter documents"),
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
) -> List[DocumentResponse]:
    """List all ingested documents in the specified workspace."""
    return pipeline.list_documents(workspace_id=workspace_id)

@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
) -> DocumentResponse:
    """Get metadata and ingestion status for a specific document."""
    doc = pipeline.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.delete("/{document_id}")
def delete_document(
    document_id: str,
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
):
    """Delete a document and purge all its chunk vectors from storage."""
    success = pipeline.delete_document(document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found or already deleted")
    # Clean up any stored file from disk
    file_pattern = os.path.join(settings.DOCUMENTS_DIR, f"{document_id}*")
    for f in glob.glob(file_pattern):
        try:
            os.remove(f)
        except OSError:
            pass
    return {"message": f"Document {document_id} and its vectors successfully deleted."}
