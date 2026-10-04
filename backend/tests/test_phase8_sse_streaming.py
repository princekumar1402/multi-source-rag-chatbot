import asyncio
import threading
import json
import pytest
import uuid
import time
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.schemas.ingestion_job import IngestionEvent, IngestionEventType
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.ingestion_job_repo import IngestionJobRepository
from backend.app.services.ingestion.event_bus import IngestionEventBus
from backend.app.core.dependencies import get_event_bus

client = TestClient(app)

# -----------------------------------------------------------------------------
# 1. Deterministic EventBus Unit Tests
# -----------------------------------------------------------------------------

def test_event_bus_subscribe_publish_unsubscribe():
    async def _run():
        bus = IngestionEventBus()
        job_id = f"test_job_{uuid.uuid4().hex}"

        assert bus.subscriber_count(job_id) == 0
        assert bus.total_subscribers() == 0

        queue = bus.subscribe(job_id)
        assert bus.subscriber_count(job_id) == 1
        assert bus.total_subscribers() == 1

        event = IngestionEvent(
            event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
            job_id=job_id,
            status="processing",
            stage="extracting",
            progress=0.25
        )

        dispatched = bus.publish(job_id, event)
        assert dispatched == 1

        received = queue.get_nowait()
        assert received.event_type == "job_stage_changed"
        assert received.stage == "extracting"
        assert received.progress == 0.25

        bus.unsubscribe(job_id, queue)
        assert bus.subscriber_count(job_id) == 0
        assert bus.total_subscribers() == 0

    asyncio.run(_run())

def test_event_bus_threadsafe_publishing():
    async def _run():
        bus = IngestionEventBus()
        job_id = f"test_job_thread_{uuid.uuid4().hex}"
        queue = bus.subscribe(job_id)

        event = IngestionEvent(
            event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
            job_id=job_id,
            status="processing",
            stage="embedding",
            progress=0.75
        )

        def publish_from_worker():
            bus.publish(job_id, event)

        thread = threading.Thread(target=publish_from_worker)
        thread.start()
        thread.join()

        received = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert received.stage == "embedding"
        assert received.progress == 0.75

        bus.unsubscribe(job_id, queue)

    asyncio.run(_run())

def test_event_bus_multiple_jobs_isolation():
    async def _run():
        bus = IngestionEventBus()
        job_a = f"job_a_{uuid.uuid4().hex}"
        job_b = f"job_b_{uuid.uuid4().hex}"

        q_a1 = bus.subscribe(job_a)
        q_a2 = bus.subscribe(job_a)
        q_b1 = bus.subscribe(job_b)

        assert bus.subscriber_count(job_a) == 2
        assert bus.subscriber_count(job_b) == 1

        event_a = IngestionEvent(
            event_type=IngestionEventType.JOB_STARTED.value,
            job_id=job_a,
            status="processing",
            stage="validating"
        )

        bus.publish(job_a, event_a)

        assert q_a1.get_nowait().stage == "validating"
        assert q_a2.get_nowait().stage == "validating"
        assert q_b1.empty()

        bus.unsubscribe(job_a, q_a1)
        bus.unsubscribe(job_a, q_a2)
        bus.unsubscribe(job_b, q_b1)
        assert bus.total_subscribers() == 0

    asyncio.run(_run())

# -----------------------------------------------------------------------------
# 2. SSE HTTP Endpoint & Validation Tests
# -----------------------------------------------------------------------------

def test_sse_endpoint_exists_and_404_for_nonexistent_job():
    res = client.get("/api/v1/ingestion/jobs/nonexistent_12345/events")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_sse_endpoint_workspace_isolation():
    ws_private = f"ws_private_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_private)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_private,
            source_type="pdf",
            status="pending"
        )
        db.commit()
        job_id = job.id

    # Trying to stream job with mismatched workspace_id must yield 403
    res = client.get(f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id=default")
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]

def test_sse_already_completed_job_closes_immediately():
    ws_id = f"ws_comp_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_id,
            source_type="pdf",
            status="completed",
            stage="completed",
            progress=1.0
        )
        db.commit()
        job_id = job.id

    with client.stream("GET", f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id={ws_id}") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        lines = list(response.iter_lines())

    text = "\n".join(lines)
    assert "event: current_state" in text
    assert "event: job_completed" in text
    assert '"status": "completed"' in text

def test_sse_already_failed_job_closes_immediately():
    ws_id = f"ws_fail_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_id,
            source_type="txt",
            status="failed",
            stage="extracting"
        )
        IngestionJobRepository.update_status(db, job.id, status="failed", error_message="Extraction failed.")
        db.commit()
        job_id = job.id

    with client.stream("GET", f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id={ws_id}") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    text = "\n".join(lines)
    assert "event: current_state" in text
    assert "event: job_failed" in text
    assert '"status": "failed"' in text
    assert "Extraction failed." in text

# -----------------------------------------------------------------------------
# 3. Live Streaming, Stage Changes, and Terminal Transitions
# -----------------------------------------------------------------------------

def test_sse_streams_stage_changes_and_terminates():
    ws_id = f"ws_stream_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_id,
            source_type="pdf",
            status="processing",
            stage="validating",
            progress=0.1
        )
        db.commit()
        job_id = job.id

    bus = get_event_bus()

    def publish_sequence():
        time.sleep(0.05)
        # Stage: CHUNKING
        bus.publish(job_id, IngestionEvent(
            event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
            job_id=job_id,
            status="processing",
            stage="chunking",
            progress=0.45
        ))
        time.sleep(0.05)
        # Stage: EMBEDDING
        bus.publish(job_id, IngestionEvent(
            event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
            job_id=job_id,
            status="processing",
            stage="embedding",
            progress=0.75
        ))
        time.sleep(0.05)
        # Completed
        bus.publish(job_id, IngestionEvent(
            event_type=IngestionEventType.JOB_COMPLETED.value,
            job_id=job_id,
            status="completed",
            stage="completed",
            progress=1.0
        ))

    pub_thread = threading.Thread(target=publish_sequence)
    pub_thread.start()

    with client.stream("GET", f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id={ws_id}") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    pub_thread.join()

    text = "\n".join(lines)
    assert "event: current_state" in text
    assert "event: job_stage_changed" in text
    assert '"stage": "chunking"' in text
    assert '"stage": "embedding"' in text
    assert "event: job_completed" in text

def test_sse_streams_failure_and_terminates_with_sanitized_error():
    ws_id = f"ws_fail_stream_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_id,
            source_type="web",
            status="processing",
            stage="validating",
            progress=0.1
        )
        db.commit()
        job_id = job.id

    bus = get_event_bus()

    def publish_failure():
        time.sleep(0.05)
        bus.publish(job_id, IngestionEvent(
            event_type=IngestionEventType.JOB_FAILED.value,
            job_id=job_id,
            status="failed",
            stage="extracting",
            progress=0.25,
            error="Connection to database failed: postgresql://admin:secretpass@db:5432/rag"
        ))

    pub_thread = threading.Thread(target=publish_failure)
    pub_thread.start()

    with client.stream("GET", f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id={ws_id}") as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    pub_thread.join()

    text = "\n".join(lines)
    assert "event: job_failed" in text
    # Sanitizer must ensure sensitive DB credentials are never streamed
    assert "secretpass" not in text

def test_sse_reconnection_queries_authoritative_db_state():
    ws_id = f"ws_reconnect_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_id,
            source_type="docx",
            status="processing",
            stage="validating",
            progress=0.1
        )
        db.commit()
        job_id = job.id

        # Job progresses in DB while frontend was disconnected
        IngestionJobRepository.update_stage(db, job_id, stage="indexing", progress=0.9)
        db.commit()

    bus = get_event_bus()

    # Finish the job after connection so stream terminates cleanly
    def complete_later():
        time.sleep(0.05)
        bus.publish(job_id, IngestionEvent(
            event_type=IngestionEventType.JOB_COMPLETED.value,
            job_id=job_id,
            status="completed",
            stage="completed",
            progress=1.0
        ))

    thread = threading.Thread(target=complete_later)
    thread.start()

    # Reconnect stream
    with client.stream("GET", f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id={ws_id}") as response:
        lines = list(response.iter_lines())

    thread.join()

    text = "\n".join(lines)
    assert "event: current_state" in text
    assert '"stage": "indexing"' in text
    assert '"progress": 0.9' in text
    assert "event: job_completed" in text

def test_sse_subscriber_cleanup_on_completion():
    ws_id = f"ws_clean_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job = IngestionJobRepository.create(
            db=db,
            workspace_id=ws_id,
            source_type="pdf",
            status="processing",
            stage="validating",
            progress=0.1
        )
        db.commit()
        job_id = job.id

    bus = get_event_bus()

    def complete_job():
        time.sleep(0.05)
        # Verify subscriber was registered
        bus.publish(job_id, IngestionEvent(
            event_type=IngestionEventType.JOB_COMPLETED.value,
            job_id=job_id,
            status="completed",
            stage="completed",
            progress=1.0
        ))

    thread = threading.Thread(target=complete_job)
    thread.start()

    with client.stream("GET", f"/api/v1/ingestion/jobs/{job_id}/events?workspace_id={ws_id}") as response:
        _ = list(response.iter_lines())

    thread.join()

    # Once stream terminates, the queue MUST be unsubscribed
    assert bus.subscriber_count(job_id) == 0

def test_sse_multiple_simultaneous_jobs():
    ws_id = f"ws_multi_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        job1 = IngestionJobRepository.create(
            db=db, workspace_id=ws_id, source_type="pdf", status="processing", stage="validating"
        )
        job2 = IngestionJobRepository.create(
            db=db, workspace_id=ws_id, source_type="youtube", status="processing", stage="validating"
        )
        db.commit()
        id1, id2 = job1.id, job2.id

    bus = get_event_bus()

    def stream_job(j_id, out_list):
        with client.stream("GET", f"/api/v1/ingestion/jobs/{j_id}/events?workspace_id={ws_id}") as response:
            out_list.extend(list(response.iter_lines()))

    lines1 = []
    lines2 = []
    t1 = threading.Thread(target=stream_job, args=(id1, lines1))
    t2 = threading.Thread(target=stream_job, args=(id2, lines2))
    t1.start()
    t2.start()

    time.sleep(0.05)
    # Publish distinct stage to job 1 and job 2
    bus.publish(id1, IngestionEvent(
        event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
        job_id=id1,
        status="processing",
        stage="chunking",
        progress=0.45
    ))
    bus.publish(id2, IngestionEvent(
        event_type=IngestionEventType.JOB_STAGE_CHANGED.value,
        job_id=id2,
        status="processing",
        stage="extracting",
        progress=0.25
    ))

    time.sleep(0.05)
    bus.publish(id1, IngestionEvent(
        event_type=IngestionEventType.JOB_COMPLETED.value,
        job_id=id1,
        status="completed",
        stage="completed",
        progress=1.0
    ))
    bus.publish(id2, IngestionEvent(
        event_type=IngestionEventType.JOB_COMPLETED.value,
        job_id=id2,
        status="completed",
        stage="completed",
        progress=1.0
    ))

    t1.join()
    t2.join()

    text1 = "\n".join(lines1)
    text2 = "\n".join(lines2)

    assert '"stage": "chunking"' in text1
    assert '"stage": "chunking"' not in text2
    assert '"stage": "extracting"' in text2
    assert '"stage": "extracting"' not in text1
