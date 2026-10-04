# Phase 4 Database Architecture Specification: Production Database Persistence & Structured Storage

**Document Version:** 1.0.0-PROD  
**Phase:** Phase 4 — Production Database Persistence & Structured Storage  
**Component:** Relational Data Model, Repositories, Alembic Migrations, and Vector/Keyword Synchronization  

---

## 1. Current Persistence Architecture (Phase 1–3 Baseline)

In Phases 1 through 3, the multi-source RAG system was built with:
- **Vector Persistence:** `FAISSVectorStore` storing dense embeddings on disk via `faiss.write_index()` (`faiss_index.bin`) and serializing Python `DocumentChunk` metadata via `pickle` (`faiss_chunks.pkl`).
- **Keyword Index:** `BM25Retriever` indexing tokenized chunk contents in memory, bootstrapped at runtime startup from `FAISSVectorStore.get_all_chunks()`.
- **RAG Pipeline:** `RAGEngine` orchestrating query rewriting, hybrid retrieval with Reciprocal Rank Fusion (RRF), cross-encoder reranking, context selection with deduplication, and grounded LLM generation with exact source citations (timestamps, page numbers, row/sheet references).

---

## 2. Current In-Memory State & Limitations

Prior to Phase 4, structured application metadata was kept in transient memory:
- **Document Registry:** Stored in `IngestionPipeline.documents_db` as an in-memory dictionary `Dict[str, DocumentResponse]`. Restarting the backend server purged all document metadata, leaving disk vectors disconnected from application document records.
- **Workspaces:** Identified only by string tags (`workspace_id`), with no persisted workspace entity, creation timestamps, ownership metadata, or relational constraints.
- **Conversations & Chat History:** Chat turns (`ChatTurn`) existed strictly within individual HTTP request payloads (`RAGQueryRequest.history`). No persistent conversation entities, message logs, latency metrics, or user/assistant turn persistence existed.
- **Ingestion Jobs:** Ingestion state transitions (`PROCESSING`, `READY`, `FAILED`) were updated in-place on the transient document dictionary without job execution records, timestamps, retry counts, or worker tracking.
- **Relational Integrity:** No foreign keys, cascading deletion guarantees, or ACID transactions existed between workspaces, documents, chunks, and sessions.

---

## 3. Proposed PostgreSQL Architecture

Phase 4 replaces the transient in-memory dictionary with a transactional relational database schema managed via **SQLAlchemy 2.0 (Modern Declarative Base with `Mapped` and `mapped_column`)** and **Alembic**.

### Key Architectural Pillars:
1. **Authoritative Source of Truth:** PostgreSQL is the authoritative system of record for structured entities: Workspaces, Documents, Chunks, Conversations, Messages, and Ingestion Jobs.
2. **Retrieval Index Role for FAISS & BM25:** FAISS remains the dense vector index and BM25 remains the lexical keyword index. Neither FAISS nor BM25 serves as the source of truth for business metadata.
3. **Repository Pattern:** Database transactions and queries are encapsulated in dedicated repositories (`WorkspaceRepository`, `DocumentRepository`, `ChunkRepository`, `ConversationRepository`, `MessageRepository`, `IngestionJobRepository`). Business logic, loaders, RAG engines, and API routes never execute ad-hoc ORM queries.
4. **Session Life-Cycle & Transaction Management:** FastAPI dependency injection provides scoped database sessions (`get_db`) ensuring clear unit-of-work transaction boundaries and automatic rollback upon exceptions.

---

## 4. Database Entities & Schema Definition

The database schema defines 6 core entities:

```text
┌─────────────────┐
│    Workspace    │
└────────┬────────┘
         │ 1:N
         ├───────────────────────────────┬──────────────────────────────┐
         ▼                               ▼                              ▼
┌─────────────────┐             ┌─────────────────┐            ┌─────────────────┐
│    Document     │             │  Conversation   │            │  IngestionJob   │
└────────┬────────┘             └────────┬────────┘            └─────────────────┘
         │ 1:N                           │ 1:N
         ▼                               ▼
┌─────────────────┐             ┌─────────────────┐
│      Chunk      │             │     Message     │
└─────────────────┘             └─────────────────┘
```

### 4.1. Workspaces (`workspaces`)
Represents an isolated multi-tenant knowledge workspace.
- `id` (VARCHAR(36), PK): UUID string.
- `name` (VARCHAR(255), NOT NULL): Human-readable workspace name.
- `description` (TEXT, NULLABLE): Optional workspace description.
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC creation timestamp.
- `updated_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC modification timestamp.

### 4.2. Documents (`documents`)
Represents an ingested knowledge artifact (PDF, DOCX, TXT, Markdown, CSV, XLSX, Web URL, YouTube video).
- `id` (VARCHAR(36), PK): Logical document UUID.
- `workspace_id` (VARCHAR(36), FK -> `workspaces.id` ON DELETE CASCADE, NOT NULL).
- `source_type` (VARCHAR(32), NOT NULL): `web`, `youtube`, `pdf`, `docx`, `txt`, `markdown`, `csv`, `xlsx`.
- `title` (VARCHAR(512), NOT NULL): Document title.
- `file_name` (VARCHAR(512), NULLABLE): Name of uploaded file.
- `source_url` (TEXT, NULLABLE): Original URL for web or YouTube.
- `content_hash` (VARCHAR(64), NOT NULL): SHA-256 hash of extracted content/file bytes for deduplication.
- `status` (VARCHAR(32), NOT NULL, DEFAULT 'pending'): `pending`, `processing`, `ready`, `failed`, `deleted`.
- `size_bytes` (BIGINT, NULLABLE): Size in bytes.
- `chunk_count` (INTEGER, NOT NULL, DEFAULT 0): Count of extractable chunks.
- `error_message` (TEXT, NULLABLE): Detailed error message if status is `failed`.
- `doc_metadata` (JSON/JSONB, NOT NULL, DEFAULT '{}'): Source-specific metadata (author, headers, video duration, sheet names).
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.
- `updated_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.

### 4.3. Chunks (`chunks`)
Persists all granular textual segments along with complete citation metadata for Phase 3 grounded attribution.
- `id` (VARCHAR(64), PK): Stable logical chunk identifier (e.g. `docId_chunkIndex` or UUID). Matches FAISS chunk ID.
- `document_id` (VARCHAR(36), FK -> `documents.id` ON DELETE CASCADE, NOT NULL).
- `workspace_id` (VARCHAR(36), FK -> `workspaces.id` ON DELETE CASCADE, NOT NULL).
- `chunk_index` (INTEGER, NOT NULL): Sequential index within the parent document.
- `text` (TEXT, NOT NULL): Plain text chunk content.
- `content_hash` (VARCHAR(64), NULLABLE): SHA-256 hash of chunk text.
- `source_type` (VARCHAR(32), NOT NULL): Source format.
- `source_name` (VARCHAR(512), NOT NULL): Human-readable source title for citations.
- `file_name` (VARCHAR(512), NULLABLE): File name.
- `source_url` (TEXT, NULLABLE): Source URL.
- `page_number` (INTEGER, NULLABLE): 1-indexed page number (PDFs).
- `page_index` (INTEGER, NULLABLE): 0-indexed page number.
- `sheet_name` (VARCHAR(255), NULLABLE): Worksheet tab name (Excel).
- `row_number` (INTEGER, NULLABLE): Row index (CSV/Excel).
- `timestamp_str` (VARCHAR(64), NULLABLE): Formatted MM:SS span (YouTube).
- `start_time` (FLOAT, NULLABLE): Start offset in seconds.
- `end_time` (FLOAT, NULLABLE): End offset in seconds.
- `section_title` (VARCHAR(512), NULLABLE): Markdown/DOCX heading context.
- `token_count` (INTEGER, NULLABLE): Token estimate.
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.

### 4.4. Conversations (`conversations`)
Represents an ongoing chat thread within a workspace.
- `id` (VARCHAR(36), PK): UUID.
- `workspace_id` (VARCHAR(36), FK -> `workspaces.id` ON DELETE CASCADE, NOT NULL).
- `title` (VARCHAR(255), NOT NULL, DEFAULT 'New Conversation'): Conversation title.
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.
- `updated_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.

### 4.5. Messages (`messages`)
Represents a user query or assistant response turn.
- `id` (VARCHAR(36), PK): UUID.
- `conversation_id` (VARCHAR(36), FK -> `conversations.id` ON DELETE CASCADE, NOT NULL).
- `role` (VARCHAR(32), NOT NULL): `user`, `assistant`, or `system`.
- `content` (TEXT, NOT NULL): Message text content.
- `msg_metadata` (JSON/JSONB, NOT NULL, DEFAULT '{}'): Citations, query rewriting debug, latency breakdown, retrieved chunk count.
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.

### 4.6. Ingestion Jobs (`ingestion_jobs`)
Persists the audit trail and lifecycle state of asynchronous or synchronous ingestion tasks.
- `id` (VARCHAR(36), PK): UUID.
- `workspace_id` (VARCHAR(36), FK -> `workspaces.id` ON DELETE CASCADE, NOT NULL).
- `document_id` (VARCHAR(36), FK -> `documents.id` ON DELETE CASCADE, NULLABLE).
- `status` (VARCHAR(32), NOT NULL, DEFAULT 'pending'): `pending`, `processing`, `completed`, `failed`.
- `source_type` (VARCHAR(32), NOT NULL): Ingestion source format.
- `started_at` (TIMESTAMP WITH TIME ZONE, NULLABLE): UTC timestamp when processing began.
- `completed_at` (TIMESTAMP WITH TIME ZONE, NULLABLE): UTC timestamp when finished or failed.
- `error_message` (TEXT, NULLABLE): Failure details.
- `retry_count` (INTEGER, NOT NULL, DEFAULT 0): Retry attempts.
- `created_at` (TIMESTAMP WITH TIME ZONE, NOT NULL): UTC timestamp.

---

## 5. Relationships & Foreign Keys

| Parent Table | Child Table | Foreign Key Column | On Delete Cascade | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `workspaces` | `documents` | `documents.workspace_id` | CASCADE | Purging a workspace purges all its documents. |
| `workspaces` | `chunks` | `chunks.workspace_id` | CASCADE | Chunks belong to their workspace. |
| `workspaces` | `conversations` | `conversations.workspace_id` | CASCADE | Purging a workspace purges all conversations. |
| `workspaces` | `ingestion_jobs` | `ingestion_jobs.workspace_id` | CASCADE | Jobs belong to workspace. |
| `documents` | `chunks` | `chunks.document_id` | CASCADE | Deleting a document purges all its chunks immediately. |
| `documents` | `ingestion_jobs` | `ingestion_jobs.document_id` | CASCADE | Deleting document cleans up job logs. |
| `conversations` | `messages` | `messages.conversation_id` | CASCADE | Deleting a conversation deletes all chat turns. |

---

## 6. Primary Keys, Unique Constraints & Indexes

### Primary Keys:
- All tables utilize a unique String/UUID primary key (`id`).

### Unique Constraints:
1. `uq_document_workspace_hash`: `UNIQUE (workspace_id, content_hash)` on `documents` preventing duplicate content ingestion within the same workspace.
2. `uq_chunk_doc_index`: `UNIQUE (document_id, chunk_index)` on `chunks` enforcing strict sequential chunk integrity per document.

### Performance Indexes:
- `ix_documents_workspace_id`: Accelerates workspace document listing.
- `ix_documents_content_hash`: Accelerates deduplication lookups.
- `ix_documents_status`: Enables filtering active vs failed/deleted docs.
- `ix_chunks_document_id`: Accelerates chunk retrieval by document.
- `ix_chunks_workspace_id`: Accelerates workspace chunk queries.
- `ix_conversations_workspace_id`: Accelerates workspace conversation listing.
- `ix_messages_conversation_id_created_at`: Efficiently loads chronological conversation history (`ORDER BY created_at ASC`).
- `ix_ingestion_jobs_workspace_status`: Facilitates querying active or pending ingestion tasks.

---

## 7. Cascade Behavior & Safe Deletion

- When a `Document` is deleted via the API, SQLAlchemy's `cascade="all, delete-orphan"` along with database-level `ON DELETE CASCADE` guarantees that no orphaned records remain in `chunks` or `ingestion_jobs`.
- Application-level coordination ensures that FAISS index entries and BM25 index tokens are excised before database transaction commit, preventing phantom citations.

---

## 8. Transaction Boundaries & Unit of Work

- All database mutations operate within explicit transaction boundaries.
- FastAPI dependency `get_db` yields a database session. On exit without error, changes commit. On unhandled exception, `session.rollback()` is invoked.
- Ingestion steps operate as follows:
  1. Transaction 1: Create Document in `PENDING` status and IngestionJob in `PENDING` status. Commit.
  2. Execution: Extraction, chunking, embedding, FAISS indexing, BM25 indexing.
  3. Transaction 2: Bulk insert `chunks`, update Document status to `READY` (or `FAILED`), update IngestionJob status to `COMPLETED` (or `FAILED`). Commit.
  If an exception occurs during step 2, Document and Job are updated to `FAILED` with the sanitized error message.

---

## 9. Migration Strategy (Alembic)

- Alembic is initialized with a standard directory structure (`backend/alembic/`) and `alembic.ini`.
- `env.py` binds to the application `Base.metadata` and fetches `settings.DATABASE_URL`.
- Clean bidirectional migrations:
  - `alembic upgrade head`
  - `alembic downgrade -1`
- Schema changes are strictly code-reviewed and revision-tracked.

---

## 10. FAISS ↔ PostgreSQL Relationship & Consistency

```text
    PostgreSQL Document (id="doc-123")
             │
             ▼
    PostgreSQL Chunks (id="chunk-abc", chunk_index=0, text="...", page_number=2)
             │
      ┌──────┴─────────────────────────────────┐
      ▼                                        ▼
FAISS Vector Index                      BM25 Inverted Index
(vector embedding, chunk_id="chunk-abc") (tokens, chunk_id="chunk-abc")
      │                                        │
      └──────────────────┬─────────────────────┘
                         ▼
               Retrieved chunk_id="chunk-abc"
                         │
                         ▼
        PostgreSQL / ChunkMetadata Lookup
                         │
                         ▼
      Citation: Source Title (Page 2), Snippet
```
- **Consistent ID Mapping:** The logical `chunk_id` assigned when chunking is identical across PostgreSQL `Chunk.id`, `DocumentChunk.chunk_id`, and FAISS metadata.
- **Citation Preservation:** The Phase 3 citation formatter relies directly on `chunk.metadata` which is populated with 100% fidelity from PostgreSQL `Chunk` columns (`page_number`, `timestamp_str`, `sheet_name`, `row_number`, `section_title`).

---

## 11. BM25 ↔ PostgreSQL Relationship

- Upon server startup, `BM25Retriever` can be bootstrapped from PostgreSQL chunks or vector store chunks.
- During ingestion, newly created chunks are inserted into PostgreSQL and concurrently indexed into `BM25Retriever`.
- During document deletion, `BM25Retriever.remove_document(document_id)` removes document terms from the BM25 inverted index.

---

## 12. Document Deletion Lifecycle

```text
DELETE /api/v1/documents/{document_id}
                   │
                   ▼
Check Document existence in PostgreSQL
                   │
                   ├──> Not Found: Return 404
                   │
                   ▼
1. vector_store.delete_document(document_id)  --> Rebuilds FAISS index without doc's vectors
2. bm25_retriever.remove_document(document_id) --> Removes from keyword inverted index
3. chunk_repository.delete_by_document(db, document_id)
4. document_repository.delete(db, document_id)  --> Cascades remaining relational items
                   │
                   ▼
Commit DB Transaction & Return 200 OK
```

---

## 13. Workspace Isolation

- Every query against `documents`, `chunks`, `conversations`, and `ingestion_jobs` filters strictly by `workspace_id`.
- Dense retrieval in FAISS applies metadata filter: `{"workspace_id": request.workspace_id}`.
- Lexical retrieval in BM25 filters candidates by `workspace_id`.
- A query to Workspace A can never retrieve chunks or citations from Workspace B.

---

## 14. Conversation Persistence & Chat History

When `RAGQueryRequest.conversation_id` is supplied:
1. Verify Conversation belongs to `workspace_id` (create if not found).
2. Load last $N$ turns from `MessageRepository.list_by_conversation(conversation_id, limit=10)`.
3. Format loaded messages into `history: List[ChatTurn]`.
4. Run conversational query rewriting using loaded history.
5. Perform hybrid retrieval, reranking, and grounded answer synthesis.
6. Persist User Message (`role="user"`, `content=question`).
7. Persist Assistant Message (`role="assistant"`, `content=answer`, `msg_metadata={"citations": [...], "latency": {...}}`).
8. Return `RAGQueryResponse` to client.

If `conversation_id` is null, preserve Phase 3 behavior (using `request.history` passed in the payload).

---

## 15. Ingestion Status Persistence & Lifecycle

The state machine for documents:
```text
  [PENDING]
      │
      ▼
 [PROCESSING]
      │
   ┌──┴─────────────┐
   ▼                ▼
[READY]          [FAILED]
   │
   ▼
[DELETED]
```
The state machine for ingestion jobs:
```text
  [PENDING]  ──>  [PROCESSING]  ──>  [COMPLETED]
                                └──>  [FAILED]
```

---

## 16. Failure & Retry Behavior

- If extraction or chunking raises an exception:
  - Document status -> `FAILED`, `error_message` -> detailed sanitized error.
  - Ingestion Job status -> `FAILED`, `completed_at` -> now, `error_message` -> error.
- FAISS vectors are added only if extraction and chunking succeed.
- Partial chunks are not inserted into PostgreSQL if embedding fails.

---

## 17. Backward Compatibility

- Existing API schemas (`DocumentResponse`, `RAGQueryRequest`, `RAGQueryResponse`) remain 100% backward compatible.
- All 35 Phase 3 tests continue to pass without regression.
- Endpoints accept default `workspace_id="default"`. If workspace `"default"` does not exist in the database, it is automatically created.

---

## 18. Technology Choices & Configuration

- **ORM:** SQLAlchemy 2.0 with type-annotated declarations (`Mapped`, `mapped_column`).
- **Driver:** `psycopg2-binary` for synchronous PostgreSQL, with seamless SQLite dialect compatibility.
- **Migrations:** Alembic.
- **Docker:** `docker-compose.yml` declaring `postgres` service using `postgres:16-alpine`.
- **Environment:** `DATABASE_URL` in `.env` and `backend/app/core/config.py`.
