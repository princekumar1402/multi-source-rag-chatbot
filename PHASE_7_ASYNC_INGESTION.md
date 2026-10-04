# Phase 7 — Asynchronous Ingestion & Background Job Processing

## Overview & Architecture

Phase 7 transforms the Multi-Source RAG platform's document, webpage, and YouTube ingestion workflows from synchronous, request-blocking operations into an asynchronous, resilient, background-job execution architecture.

The HTTP request lifecycle is completely decoupled from extraction, chunking, embedding, and vector indexing. Clients receive an immediate `202 Accepted` response with an `IngestionJobResponse` containing `job_id`, `document_id`, `status: "pending"`, and initial stage `validating`.

---

## 1. Architecture Flow

```
                Client (Browser / API Client)
                           │
                           │ POST /documents/upload or /url or /youtube
                           ▼
                  FastAPI Route Handler
                           │
                           ▼
                 IngestionJobService
          ┌────────────────┴────────────────┐
          │                                 │
   Validate & Hash               Create Document (PENDING)
          │                      Create IngestionJob (PENDING)
          │                                 │
          │                        Commit DB Transaction
          │                                 │
          └────────────────┬────────────────┘
                           │ Returns immediately with job_id (HTTP 202)
                           │ Schedules background task
                           ▼
                  IngestionJobRunner
                           │
       ┌───────────────────┼───────────────────┐
       ▼                   ▼                   ▼
  Stage: EXTRACTING   Stage: CHUNKING    Stage: PERSISTING
  (Loaders: PDF,      (MetadataAware     (Clean previous +
   DOCX, Web, YT)      Chunker)           Write Chunks to DB)
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
  Stage: EMBEDDING                        Stage: INDEXING
  (HuggingFace Embedder)                  (Atomic update to
                                           FAISS & BM25)
                           │
                           ▼
                   Stage: FINALIZING
             (Consistency check: DB vs Index)
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
         [SUCCESS]                  [FAILURE]
     Doc status: READY          Doc status: FAILED
     Job status: COMPLETED      Job status: FAILED
                                Clean up FAISS/BM25/DB
```

---

## 2. Ingestion Job State Machine

### Job Lifecycle
```
PENDING ──► PROCESSING ──► COMPLETED
                 │
                 └──► FAILED ──(Retry)──► PENDING
```

### Document Synchronization
- `Job: PENDING / PROCESSING` $\rightarrow$ `Document: PROCESSING`
- `Job: COMPLETED` $\rightarrow$ `Document: READY`
- `Job: FAILED` $\rightarrow$ `Document: FAILED`

### Detailed Stages
1. `VALIDATING`: Verifies file format, content header magic bytes, size limits, or URL normalization.
2. `EXTRACTING`: Executes the appropriate loader (`PDFLoader`, `DOCXLoader`, `WebLoader`, `YouTubeLoader`, etc.).
3. `CHUNKING`: Splits document content into semantic chunks while preserving hierarchical metadata (page numbers, section titles, video timestamps).
4. `PERSISTING`: Commits chunk records into PostgreSQL, purging any stale chunks if retrying.
5. `EMBEDDING`: Generates normalized dense vector embeddings.
6. `INDEXING`: Purges old vectors/tokens and indexes chunks into FAISS and BM25.
7. `FINALIZING`: Validates that PostgreSQL chunk counts match indexed vector counts before marking the document `READY`.
8. `COMPLETED`: Ingestion successfully finished.

---

## 3. API Endpoints

### 1. File Upload (Async)
- **Method**: `POST /api/v1/documents/upload`
- **Status**: `202 Accepted`
- **Request**: Multipart form data (`file`, `workspace_id`, optional `title`)
- **Response**:
  ```json
  {
    "job_id": "06db4215-99d7-4632-9cb2-9382f71881cb",
    "document_id": "a2512f43-4e4b-449e-b9b0-96f1d227918a",
    "workspace_id": "default",
    "status": "pending",
    "stage": "validating",
    "progress": 0.05,
    "error": null,
    "source_type": "pdf",
    "retry_count": 0,
    "created_at": "2026-09-30T17:45:00Z"
  }
  ```

### 2. URL / Webpage Ingestion (Async)
- **Method**: `POST /api/v1/documents/url`
- **Status**: `202 Accepted`
- **Request**: JSON `{"url": "...", "workspace_id": "default", "title": "..."}`
- **Response**: `IngestionJobResponse`

### 3. YouTube Ingestion (Async)
- **Method**: `POST /api/v1/documents/youtube`
- **Status**: `202 Accepted`
- **Request**: JSON `{"url": "...", "workspace_id": "default", "title": "..."}`
- **Response**: `IngestionJobResponse`

### 4. Job Status & Progress Polling
- **Method**: `GET /api/v1/ingestion/jobs/{job_id}`
- **Response**:
  ```json
  {
    "job_id": "06db4215-99d7-4632-9cb2-9382f71881cb",
    "document_id": "a2512f43-4e4b-449e-b9b0-96f1d227918a",
    "workspace_id": "default",
    "status": "processing",
    "stage": "embedding",
    "progress": 0.75,
    "error": null,
    "source_type": "pdf",
    "retry_count": 0,
    "created_at": "2026-09-30T17:45:00Z",
    "started_at": "2026-09-30T17:45:01Z"
  }
  ```

### 5. Job Retry
- **Method**: `POST /api/v1/ingestion/jobs/{job_id}/retry`
- **Status**: `200 OK`
- **Behavior**:
  - Restricts retry strictly to `FAILED` jobs.
  - Verifies no active concurrent job is processing the same document.
  - Cleans up partial chunks, FAISS vectors, and BM25 tokens.
  - Increments `retry_count`, resets status to `pending`, and schedules background execution.

---

## 4. Concurrency Protection & Transaction Safety

1. **Database State Locking**:
   - `IngestionJobRepository.find_active_by_document(db, document_id)` checks if another job is in `pending` or `processing` state for the same document.
   - Prevents race conditions and duplicate concurrent embeddings.
2. **Partial State Cleanup on Exception**:
   - If extraction, embedding, or indexing fails at any stage:
     - `self.pipeline.vector_store.delete_document(doc.id)`
     - `self.pipeline.keyword_retriever.remove_document(doc.id)`
     - `ChunkRepository.delete_by_document(db, doc.id)`
     - Document marked `FAILED`; Job marked `FAILED`.
   - Broken documents never leak into vector stores or keyword indices.
3. **Idempotency Guarantees**:
   - Chunks are keyed deterministically by `(document_id, chunk_index)`.
   - Re-running or retrying a job purges previous chunks before insertion, preventing duplicate vectors in FAISS or duplicate tokens in BM25.

---

## 5. Retrieval Safety & Scoping Integration

- **Strict Document Status Filter**:
  - `POST /api/v1/chat/query` validates that only documents with `status == "ready"` can ever be searched.
  - Documents in `pending`, `processing`, or `failed` status are 100% excluded from FAISS candidate selection, BM25 keyword matching, and RAG context.
- **Frontend Dropdown Isolation**:
  - In `ChatView.tsx`, the search-scope selector filters strictly by `documents.filter(d => d.status === 'ready')`.

---

## 6. Frontend Polling & UX

- **No SSE / No WebSockets**: Pure HTTP polling at 1000ms intervals until terminal status (`completed` or `failed`).
- **Live Visual Feedback**:
  - `ActiveJobCard` displays stage progression (`Extracting`, `Chunking`, `Embedding`, `Indexing`, `Finalizing`).
  - Coarse progress bar based on completed pipeline stages.
  - Upon completion, automatically refreshes `DocumentList` and system health.
  - Upon failure, displays error message and an immediate **"Retry Ingestion"** button.

---

## 7. Migration Path to Distributed Workers (Celery / RabbitMQ / Redis)

The domain architecture was deliberately decoupled from FastAPI `BackgroundTasks`:

```
FastAPI Route  ──►  IngestionJobService  ──►  IngestionJobRunner  ──►  Pipeline
```

To migrate to Celery:
1. Replace `background_tasks.add_task(runner.run_job, job_id=...)` with:
   `celery_app.send_task("tasks.run_ingestion_job", args=[job_id])`.
2. The Celery worker task simply executes:
   ```python
   @celery_app.task(name="tasks.run_ingestion_job")
   def celery_run_job(job_id: str):
       runner = get_ingestion_job_runner()
       runner.run_job(job_id=job_id)
   ```
3. Zero domain, database, loader, or vector store code requires rewriting.
