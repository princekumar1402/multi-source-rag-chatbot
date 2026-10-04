from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional

from backend.app.schemas.ingestion_job import IngestionJobResponse
from backend.app.core.dependencies import get_ingestion_job_service
from backend.app.services.ingestion.job_service import IngestionJobService

router = APIRouter()

@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_job_status(
    job_id: str,
    job_service: IngestionJobService = Depends(get_ingestion_job_service)
) -> IngestionJobResponse:
    """Retrieves the status, stage, and execution progress for an IngestionJob."""
    job = job_service.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job '{job_id}' not found.")
    return job

@router.post("/jobs/{job_id}/retry", response_model=IngestionJobResponse)
def retry_failed_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    job_service: IngestionJobService = Depends(get_ingestion_job_service)
) -> IngestionJobResponse:
    """
    Safely retries a FAILED ingestion job.
    Resets the job status to pending, cleans up any previous partial state,
    and schedules execution in the background.
    """
    try:
        job_resp, needs_processing = job_service.retry_job(job_id)
        if needs_processing:
            background_tasks.add_task(
                job_service.runner.run_job,
                job_id=job_resp.job_id
            )
        return job_resp
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retry job: {str(e)}")
