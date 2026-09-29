from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional

from backend.app.schemas.document import (
    DocumentResponse,
    DocumentIngestURLRequest,
    DocumentIngestYouTubeRequest,
    DocumentStatus
)
from backend.app.core.dependencies import get_ingestion_pipeline
from backend.app.services.ingestion.pipeline import IngestionPipeline

router = APIRouter()

@router.post("/url", response_model=DocumentResponse)
def ingest_web_url(
    payload: DocumentIngestURLRequest,
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
) -> DocumentResponse:
    """Ingest, clean, chunk, embed, and index a webpage or article URL."""
    try:
        doc = pipeline.process_url(
            url=payload.url,
            workspace_id=payload.workspace_id,
            custom_title=payload.title
        )
        if doc.status == DocumentStatus.FAILED:
            raise HTTPException(status_code=400, detail=doc.error_message or "Ingestion failed")
        return doc
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal ingestion error: {str(e)}")

@router.post("/youtube", response_model=DocumentResponse)
def ingest_youtube_url(
    payload: DocumentIngestYouTubeRequest,
    pipeline: IngestionPipeline = Depends(get_ingestion_pipeline)
) -> DocumentResponse:
    """Ingest, extract transcript, chunk, embed, and index a YouTube video."""
    try:
        doc = pipeline.process_url(
            url=payload.url,
            workspace_id=payload.workspace_id,
            custom_title=payload.title
        )
        if doc.status == DocumentStatus.FAILED:
            raise HTTPException(status_code=400, detail=doc.error_message or "YouTube ingestion failed")
        return doc
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
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
    return {"message": f"Document {document_id} and its vectors successfully deleted."}
