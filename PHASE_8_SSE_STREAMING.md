# Phase 8 — Server-Sent Events (SSE) Streaming & Real-Time Ingestion UX

## Overview

Phase 8 replaces the frontend's legacy 1-second HTTP polling mechanism (`GET /api/v1/ingestion/jobs/{job_id}`) with real-time **Server-Sent Events (SSE)** streaming (`GET /api/v1/ingestion/jobs/{job_id}/events`).

The PostgreSQL database and `IngestionJobRunner` remain the authoritative source of truth for job execution, stage tracking, idempotency, and transactional consistency.

---

## 1. SSE Event Architecture

```text
[ Document Ingestion Requested ] (File / URL / YouTube)
                ↓
    IngestionJobService (db.commit)
                ↓
    IngestionJobRunner (Background Worker)
                ↓
        Stage Transitions
   (Validating → Extracting → Chunking → Persisting → Embedding → Indexing → Finalizing → Completed)
                ↓
         IngestionEventBus (publish)
                ↓
    FastAPI SSE Stream Endpoint (/jobs/{job_id}/events)
                ↓
    React EventSource (Frontend Client)
                ↓
       ActiveJobCard (Real-time UI Updates)
```

---

## 2. In-Process EventBus Design (`IngestionEventBus`)

The `IngestionEventBus` (`backend/app/services/ingestion/event_bus.py`) is a lightweight, thread-safe, decoupled event publisher designed specifically for FastAPI:

- **Decoupled Architecture**: `IngestionJobRunner` does NOT interact directly with HTTP request or response objects. It publishes strictly to `IngestionEventBus`.
- **Thread Safety**: Runner executions initiated by FastAPI `BackgroundTasks` run in worker threads. The event bus bridges thread boundaries safely via `loop.call_soon_threadsafe(_put)`.
- **Bounded Queues & Memory Safety**: Each subscriber receives a bounded `asyncio.Queue(maxsize=100)` to prevent unbounded memory growth from slow clients.
- **Leak-Free Subscription Cleanup**: When a connection closes or client disconnects, `unsubscribe(job_id, queue)` is always invoked in a `finally` block.

```python
class IngestionEventBus:
    def subscribe(self, job_id: str, max_queue_size: int = 100) -> asyncio.Queue
    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None
    def publish(self, job_id: str, event: IngestionEvent) -> int
    def subscriber_count(self, job_id: str) -> int
    def total_subscribers(self) -> int
    def clear(self) -> None
```

---

## 3. SSE Stream Endpoint

### Endpoint Signature
```http
GET /api/v1/ingestion/jobs/{job_id}/events?workspace_id={workspace_id}
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Event Payload Schema (`IngestionEvent`)
```json
{
  "event_type": "job_stage_changed",
  "job_id": "01c2b11e-0fbc-4aae-b322-820f2179005c",
  "document_id": "675524af-780d-41a8-b86b-4568b9a2b1b1",
  "workspace_id": "default",
  "status": "processing",
  "stage": "embedding",
  "progress": 0.75,
  "error": null,
  "source_type": "pdf",
  "retry_count": 0,
  "created_at": "2026-10-04T18:10:48.000000Z",
  "started_at": "2026-10-04T18:10:48.010000Z",
  "completed_at": null
}
```

### Supported Event Types
- `current_state`: Immediately transmitted upon establishing the SSE connection with authoritative database state.
- `job_created`: Published upon job creation in `pending` state.
- `job_started`: Published when worker begins execution in `validating` stage.
- `job_stage_changed`: Published at each lifecycle transition (`EXTRACTING`, `CHUNKING`, `PERSISTING`, `EMBEDDING`, `INDEXING`, `FINALIZING`).
- `job_completed`: Published when document is marked `ready` and all chunks are indexed. Closes SSE stream.
- `job_failed`: Published upon unhandled loader or indexing error with sanitized message. Closes SSE stream.

---

## 4. Connection Lifecycle & Database Authority

1. **Existence & Workspace Check**:
   - Validates that `job_id` exists in PostgreSQL (returns `404 Not Found` if missing).
   - Validates that `job.workspace_id == workspace_id` (returns `403 Forbidden` if unauthorized).
2. **Subscription First**:
   - The SSE route subscribes to `IngestionEventBus` before querying the database, eliminating race conditions.
3. **Database as Authoritative State**:
   - Immediately queries PostgreSQL and streams `event: current_state`.
   - If the job is already `completed` or `failed`, sends the terminal event and immediately terminates the stream without lingering.
4. **Heartbeat & Disconnect Handling**:
   - Sends `: keepalive\n\n` comments every 15 seconds to prevent proxy / NAT timeouts.
   - Monitors `request.is_disconnected()`. If client disconnects, terminates generator and unregisters the subscriber.

---

## 5. Security & Error Sanitization

- **Workspace Isolation**: A client cannot stream events from another workspace.
- **Credential & Secret Stripping**: All error messages passed to SSE payloads are passed through `sanitize_error_message()`:
  - Database connection strings (`postgresql://...`) and password keywords are scrubbed.
  - Python internal stack traces are redacted.
  - Raw document content and transcripts are never exposed in event streams.

---

## 6. Frontend EventSource Lifecycle & Multiple Jobs

- **No HTTP Polling**: The legacy `setInterval` 1000ms loop in `App.tsx` has been eliminated.
- **Multiple Simultaneous Jobs**:
  - `App.tsx` maintains `activeJobs: IngestionJobItem[]` and `eventSourcesRef = useRef<Map<string, () => void>>(new Map())`.
  - Multiple files or URLs can be ingested simultaneously. Each job opens an independent `EventSource` connection.
  - `ActiveJobCard` updates in real time for each job independently.
- **Terminal Handling**:
  - On `job_completed`: UI updates to completed, `EventSource` is closed, document and health states refresh, and the card auto-dismisses after 4 seconds.
  - On `job_failed`: UI displays sanitized error message, `EventSource` is closed, and the `Retry` button remains accessible.
- **Retry Handling**:
  - Clicking `Retry` triggers `/api/v1/ingestion/jobs/{job_id}/retry` and immediately attaches a fresh `EventSource` to stream the retried lifecycle.
- **Unmount Safety**:
  - On unmount, all active `EventSource` connections in `eventSourcesRef` are cleanly closed.

---

## 7. Migration Considerations (Future Distributed Workers)

In this single-instance deployment, `IngestionEventBus` operates in-process with `asyncio.Queue` and thread-safe dispatching.

To scale horizontally across multiple FastAPI backend instances or Celery workers:
- **Shared Event Broker**: Replace `IngestionEventBus` with a Redis Pub/Sub or RabbitMQ broker.
- **Runner Decoupling**: Because `IngestionJobRunner` only interacts with `publish(job_id, event)`, no changes to the ingestion domain logic or database persistence layer will be required.
- **FastAPI SSE Route**: The SSE route will subscribe to `redis.pubsub()` per `job_id`, preserving identical SSE protocols and frontend behavior.

---

## 8. Verification Results

- **Backend Pytest Suite**: **88 / 88 tests passing** (76 baseline regression tests + 12 Phase 8 SSE streaming tests).
- **Frontend Production Build**: `npm run build` completed with zero TypeScript errors and zero bundle warnings.
- **Manual Verification (A–E)**:
  - **TEST A (PDF)**: Real-time progress through all stages to `COMPLETED` over SSE.
  - **TEST B (URL/YouTube & RAG)**: Live stage updates and grounded RAG answer retrieval.
  - **TEST C (Failure)**: `job_failed` streaming with sanitized error message and clean closure.
  - **TEST D (Retry)**: Job reset, retry count increment, and new SSE stream connection.
  - **TEST E (Multiple Jobs)**: Concurrent PDF jobs streamed in parallel without cross-talk or race conditions.
