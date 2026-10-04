import asyncio
import json
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from typing import Optional

from backend.app.core.logging import logger
from backend.app.schemas.ingestion_job import IngestionJobResponse
from backend.app.core.dependencies import get_ingestion_job_service, get_event_bus
from backend.app.services.ingestion.job_service import IngestionJobService
from backend.app.services.ingestion.event_bus import IngestionEventBus
from backend.app.services.ingestion.job_runner import sanitize_error_message

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

@router.get("/jobs/{job_id}/events")
async def stream_job_events(
    job_id: str,
    request: Request,
    workspace_id: str = "default",
    job_service: IngestionJobService = Depends(get_ingestion_job_service),
    event_bus: IngestionEventBus = Depends(get_event_bus)
):
    """
    Server-Sent Events (SSE) stream for real-time ingestion job lifecycle updates.
    Validates job and workspace existence, immediately transmits authoritative database state,
    and streams live stage transitions until the job reaches a terminal state (COMPLETED / FAILED).
    """
    # 1. Validate job existence
    existing_job = job_service.get_job_status(job_id)
    if not existing_job:
        raise HTTPException(status_code=404, detail=f"Ingestion job '{job_id}' not found.")

    # 2. Enforce workspace isolation
    if existing_job.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Access denied: job does not belong to the specified workspace.")

    async def event_generator():
        def format_sse(event_type: str, data: dict) -> str:
            return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

        # Subscribe to EventBus before initial query to prevent race conditions
        queue = event_bus.subscribe(job_id)
        try:
            # PostgreSQL is the authoritative source of truth
            current = job_service.get_job_status(job_id, workspace_id=workspace_id)
            if not current:
                return

            current_payload = {
                "event_type": "current_state",
                "job_id": current.job_id,
                "document_id": current.document_id,
                "workspace_id": current.workspace_id,
                "status": current.status,
                "stage": current.stage,
                "progress": current.progress,
                "error": sanitize_error_message(current.error),
                "source_type": current.source_type,
                "retry_count": current.retry_count,
                "created_at": current.created_at.isoformat() if current.created_at else None,
                "started_at": current.started_at.isoformat() if current.started_at else None,
                "completed_at": current.completed_at.isoformat() if current.completed_at else None,
            }

            # Immediately transmit current state
            yield format_sse("current_state", current_payload)

            # If the job has already finished, send terminal event and terminate stream
            if current.status == "completed":
                yield format_sse("job_completed", current_payload)
                return
            elif current.status in ("failed", "cancelled"):
                yield format_sse("job_failed", current_payload)
                return

            # Stream subsequent live events until terminal state or client disconnect
            while True:
                if await request.is_disconnected():
                    logger.debug(f"sse_client_disconnected | job_id={job_id}")
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_dict = event.model_dump(mode="json")
                    if event_dict.get("error"):
                        event_dict["error"] = sanitize_error_message(event_dict["error"])
                    yield format_sse(event.event_type, event_dict)

                    # Terminate stream upon reaching final state
                    if event.status in ("completed", "failed", "cancelled") or event.event_type in ("job_completed", "job_failed"):
                        break
                except asyncio.TimeoutError:
                    if await request.is_disconnected():
                        break
                    # Keepalive heartbeat
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            logger.debug(f"sse_stream_cancelled | job_id={job_id}")
            raise
        finally:
            event_bus.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

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
