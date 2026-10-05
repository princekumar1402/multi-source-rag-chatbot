# PHASE 12 — PRODUCTION DOCKER & DEPLOYMENT REPORT

**Multi-Source RAG Chatbot Platform**  
**Phase Status:** COMPLETE  
**Deployment Baseline Verified:** Containerized Multi-Service Architecture (Frontend, Backend, PostgreSQL)

---

## 1. Executive Summary

Phase 12 transitions the Multi-Source RAG Chatbot from a development environment into a **reproducible, containerized, health-monitored, and production-ready system**. 

### Key Accomplishments
1. **Multi-Stage Docker Architecture**:
   - Backend: Lean Python 3.11-slim container with CPU-only PyTorch wheels (saving ~2GB CUDA overhead), non-root execution (`appuser`), and embedded entrypoint automation.
   - Frontend: Node.js 20 Alpine compilation builder paired with an optimized Alpine Nginx 1.27 web server.
2. **Production Nginx Reverse Proxy with Zero-Buffering SSE**:
   - Pre-configured Nginx reverse proxy serving static SPA assets with gzip compression.
   - Proxies `/api/` upstream to the FastAPI backend with HTTP/1.1 connection pooling, `proxy_buffering off;`, and `chunked_transfer_encoding off;` ensuring real-time Server-Sent Events (SSE) stream without delay or proxy drops.
3. **Automated Migration & Safe Startup**:
   - Integrated `backend/entrypoint.sh` executing deterministic PostgreSQL TCP availability polling, running transactional Alembic migrations (`alembic upgrade head`), and launching production Uvicorn ASGI server with signal forwarding (`SIGTERM`/`SIGINT`).
4. **Resilient Liveness & Readiness Probes**:
   - `GET /health` (liveness): Fast, non-blocking check verifying process vitality without downstream dependency waits.
   - `GET /ready` (readiness): Thorough check validating PostgreSQL connectivity, vector store indexing readiness, and embedding engine availability—**consuming zero external LLM/Groq tokens**.
5. **Durable Persistence Across Container Recreations**:
   - Database storage (`rag_platform_postgres_data`) and vector/upload storage (`rag_platform_data`) validated across full `docker compose down && docker compose up -d` lifecycle without data loss.
6. **100% Test & Regression Pass**:
   - Backend unit and integration test suite: **117/117 passed** (baseline 116 + new `/ready` probe test).
   - Frontend production build: **PASS** (`tsc && vite build` in 7.86s).
   - Production container smoke test suite: **9/9 passed**.
   - Multi-source ingestion & retry verification: **5/5 passed**.

---

## 2. Production Deployment Architecture

```text
                                INTERNET
                                   │
                                   ▼
                      [Host Port 80 / 443]
                                   │
                    ┌──────────────┴──────────────┐
                    │      Frontend Container     │
                    │         (Nginx 1.27)        │
                    │  - Static SPA Assets (dist) │
                    │  - Gzip Compression         │
                    │  - Unbuffered SSE Proxy     │
                    └──────────────┬──────────────┘
                                   │
                 Internal Network (rag_platform_network)
                                   │
                    ┌──────────────┴──────────────┐
                    │      Backend Container      │
                    │      (FastAPI + Uvicorn)    │
                    │  - Ingestion Job Runner     │
                    │  - In-Process EventBus      │
                    │  - Dual Caching Engine      │
                    │  - FAISS & BM25 Retr.       │
                    └───────┬──────────────┬──────┘
                            │              │
           ┌────────────────┘              └────────────────┐
           ▼                                                ▼
┌────────────────────────┐                       ┌─────────────────────┐
│  PostgreSQL Container  │                       │   External Services │
│      (v16-alpine)      │                       │     - Groq Cloud    │
│  - Relational Metadata │                       │     - HuggingFace   │
│  - Jobs & Workspaces   │                       │       Hub (weights) │
│  - Chunks & Status     │                       └─────────────────────┘
└────────────────────────┘
```

---

## 3. Container Breakdown & Responsibilities

| Container Name | Base Image | Build Type | Non-Root | Healthcheck Command | Exposed Ports | Responsibility |
|---|---|---|---|---|---|---|
| `rag_platform_frontend` | `nginx:1.27-alpine` | Multi-Stage (Node 20 -> Nginx) | Nginx daemon (worker unprivileged) | `wget -qO- http://127.0.0.1/healthz \|\| exit 1` | `0.0.0.0:80->80/tcp` | Serves React SPA, proxies `/api/` to backend, handles unbuffered SSE streaming |
| `rag_platform_backend` | `python:3.11-slim` | Multi-Stage (wheels builder -> runtime) | `appuser:appgroup` (UID 1000) | `curl -f http://localhost:8000/health \|\| exit 1` | `0.0.0.0:8000->8000/tcp` | Executes REST endpoints, background ingestion, hybrid RAG, caching, and embeddings |
| `rag_platform_postgres` | `postgres:16-alpine` | Official Docker Hub Image | `postgres` (UID 70) | `pg_isready -U rag_user -d rag_db` | `127.0.0.1:5434->5432/tcp` (Internal/Loopback only) | Authoritative persistent storage for documents, workspaces, chunks, and jobs |

---

## 4. Environment Variables Reference

A clean, safe template is committed as `.env.example` and `.env.docker.example`. **No credentials or secrets are baked into container images or committed to version control.**

| Variable | Default (Docker) | Purpose | Required / Optional |
|---|---|---|---|
| `APP_ENV` | `production` | Deployment environment identifier | Optional |
| `DEBUG` | `False` | Disables debug stack traces in production | Recommended |
| `DATABASE_URL` | `postgresql+psycopg2://rag_user:rag_password@postgres:5432/rag_db` | Connection string to containerized PostgreSQL | Required |
| `GROQ_API_KEY` | *(Set via host .env)* | API key for LLM generation via Groq | Required for RAG |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model name on Groq inference cloud | Optional |
| `LLM_PROVIDER` | `groq` | Active LLM inference provider | Optional |
| `EMBEDDING_PROVIDER` | `huggingface` | Embedding provider (huggingface / openai) | Optional |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Dense embedding model name | Optional |
| `VECTOR_STORE_TYPE` | `faiss` | Vector store backend (`faiss`) | Optional |
| `VECTOR_STORE_PATH` | `/app/data/vector_store` | Persistent directory for FAISS index binaries | Required |
| `CACHE_ENABLED` | `true` | Enables in-process retrieval & answer caching | Recommended |
| `CACHE_TTL_SECONDS` | `3600` | TTL for cached queries (1 hour) | Optional |
| `CACHE_MAX_SIZE` | `1000` | LRU capacity for in-process query cache | Optional |
| `DB_POOL_SIZE` | `10` | SQLAlchemy connection pool size | Optional |
| `DB_MAX_OVERFLOW` | `20` | SQLAlchemy max overflow connections | Optional |
| `RERANKER_ENABLED` | `true` | Enables Cross-Encoder re-ranking stage | Recommended |
| `RERANKER_TOP_K` | `5` | Candidates preserved after re-ranking | Optional |
| `QUERY_REWRITE_ENABLED` | `true` | Enables HyDE / contextual query rewriting | Optional |
| `CORS_ORIGINS` | `["http://localhost","http://localhost:80",...]` | JSON list of permitted browser origins | Required |
| `LOG_LEVEL` | `INFO` | Application log verbosity (`DEBUG`/`INFO`/`WARN`) | Optional |

---

## 5. Database Persistence & Migrations

### Persistence
- PostgreSQL database files reside on a dedicated named Docker volume: `rag_platform_postgres_data` mapped to `/var/lib/postgresql/data`.
- FAISS index binaries, BM25 state, and uploaded document artifacts reside on `rag_platform_data` mapped to `/app/data`.
- **Restart Verification**: Recreating the containers via `docker compose down` followed by `docker compose up -d` preserved all existing workspaces, documents, chunks, and FAISS indices with 100% integrity.

### Migrations
- Managed via Alembic (`backend/alembic`).
- Execution is baked into `backend/entrypoint.sh`:
  1. Polls PostgreSQL socket on `postgres:5432` until ready (60s safety timeout).
  2. Executes `alembic upgrade head`.
  3. Incremental migration `a1b2c3d4e5f6_add_ix_ingestion_jobs_doc_status.py` adds composite indexing on `(document_id, status)` for ingestion job polling optimization.
  4. Subsequent container starts idempotently confirm `alembic upgrade head` without race conditions or data modifications.

---

## 6. Networking & Ports

Docker network: `rag_platform_network` (bridge driver, isolated).

| Service | Internal Container Port | Host Port Mapping | Public Exposure | Rationale |
|---|---|---|---|---|
| `frontend` | 80 | `0.0.0.0:80` | **Public** | Serves static UI and proxies web traffic |
| `backend` | 8000 | `0.0.0.0:8000` | **Internal / Direct API** | Direct REST API access for external clients |
| `postgres` | 5432 | `127.0.0.1:5434` | **Localhost Only** | **NOT exposed publicly.** Bound strictly to `127.0.0.1` for local maintenance scripts without internet vulnerability. |

---

## 7. Health Checks vs. Readiness Probes

### Liveness Probe (`GET /health`)
- **Location**: `http://localhost:8000/health` (also mounted at `/api/v1/health`)
- **Criteria**: Returns `HTTP 200` instantly if the Python ASGI process is active.
- **Resource Usage**: Fast, zero external network calls, zero token consumption.

### Readiness Probe (`GET /ready`)
- **Location**: `http://localhost:8000/ready` (also mounted at `/api/v1/ready`)
- **Criteria**:
  1. Executes `SELECT 1` on PostgreSQL to confirm active connection pool.
  2. Verifies `FAISSVectorStore` is loaded in memory.
  3. Verifies `Embedder` model is active in memory.
- **Fail Response**: Returns `HTTP 503 Service Unavailable` with diagnostic payload if any component is unready.
- **Token Guarantee**: **Zero LLM tokens consumed**. Health probes never invoke Groq or external paid APIs.

---

## 8. Server-Sent Events (SSE) & Reverse Proxy Configuration

Server-Sent Events provide live ingestion progress (`validating` -> `chunking` -> `embedding` -> `indexing` -> `completed`). 

In standard Nginx setups, `proxy_buffering on;` causes events to be held in memory until the buffer fills or connection terminates, completely breaking live UI updates. 

In `frontend/nginx.conf`, the `/api/` proxy block explicitly enforces:
```nginx
location /api/ {
    proxy_pass http://backend:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # SSE streaming configuration (disable proxy buffering)
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header Connection '';
    chunked_transfer_encoding off;
    proxy_read_timeout 86400s;
}
```
**Verification**: Smoke tests confirmed real-time receipt of intermediate stages through Nginx on port 80.

---

## 9. Verification & Smoke Test Results

### 1. Automated Production Smoke Test Suite (`smoke_test_production.py`)
Targeted live containers on `http://localhost:8000` (backend) and `http://localhost:80` (frontend Nginx):

| Step | Verification Stage | Target | Result | Details |
|---|---|---|---|---|
| 1 | Backend Liveness Probe | `/health` | **PASS** | HTTP 200, status: healthy |
| 2 | Backend Readiness Probe | `/ready` | **PASS** | HTTP 200, database connected, vector store ready |
| 3 | Frontend Static Serving | `/` & `/healthz` | **PASS** | SPA index.html served, Nginx healthz returns healthy |
| 4 | Document Upload (Async) | `/api/v1/documents/upload` | **PASS** | Ingestion job queued, status=202 |
| 5 | SSE Streaming & Polling | `/api/v1/ingestion/jobs/{id}/events` | **PASS** | Real-time transitions to completed in 1.02s |
| 6 | Grounded RAG Query & Citation | `/api/v1/chat/query` | **PASS** | Grounded answer with 100% accurate citation |
| 7 | Document-Scoped Isolation | `/api/v1/chat/query` | **PASS** | Out-of-scope query returned 0 citations & grounded refusal |
| 8 | Repeated Query Caching | `/api/v1/chat/query` | **PASS** | Cache hit verified; sub-10ms response latency |
| 9 | Ingestion Failure Handling | `/api/v1/documents/upload` | **PASS** | Unsupported extension gracefully rejected with HTTP 400 |

**Result: 9/9 Tests Passed (100%)**

### 2. Multi-Source Ingestion & Robustness Suite (`verify_production_multisource.py`)
| Test | Source Type | Status | Verified Behavior |
|---|---|---|---|
| 1 | PDF Document | **PASS** | Minimal PDF generated, uploaded, chunked, embedded, queried with citation |
| 2 | Web Page (URL) | **PASS** | `https://example.com` fetched, text extracted, indexed, and queried |
| 3 | YouTube Endpoint | **PASS** | `/api/v1/documents/youtube` validated, accepted, and processed |
| 4 | Ingestion Failure | **PASS** | Non-existent domain correctly transitioned job status to `failed` |
| 5 | Ingestion Retry API | **PASS** | `POST /jobs/{id}/retry` re-queued failed job with incremented retry count |

**Result: 5/5 Tests Passed (100%)**

### 3. Container Restart & Persistence Verification
- Tested via `docker compose down` followed by `docker compose up -d`.
- **Result**: PostgreSQL records and FAISS chunk vectors preserved without data loss. `Example Domain` document remained queryable immediately upon restart.

---

## 10. Image Sizes & Resource Footprint

```text
REPOSITORY                                  TAG         COMPRESSED SIZE   VIRTUAL SIZE
rag-platform-frontend                       latest      21.0 MB           73.9 MB
rag-platform-backend                        latest      821.0 MB          3.57 GB
postgres                                    16-alpine   117.0 MB          420.0 MB
```

### Estimated Production Resource Requirements
- **Backend Container**:
  - CPU: Minimum 1.0 vCPU, Recommended 2.0 vCPU (handles CPU-based dense embeddings and cross-encoder re-ranking).
  - RAM: Minimum 2.0 GB, Recommended 4.0 GB (HuggingFace model weights + FAISS index + PyTorch runtime).
  - Disk: 10 GB persistent storage for vector stores and uploaded documents.
- **Frontend Container**:
  - CPU: 0.1 vCPU (lightweight Nginx static proxy).
  - RAM: 64 MB.
  - Disk: 100 MB.
- **PostgreSQL Container**:
  - CPU: 0.5 vCPU.
  - RAM: 512 MB - 1.0 GB.
  - Disk: 20 GB+ persistent SSD.

---

## 11. Known Limitations & Phase 17 Scaling Roadmap

### Current Limitations in Phase 12
1. **Single-Process EventBus**:
   - The SSE event bus uses an in-memory `asyncio.Queue` registry. Live streaming works seamlessly for single backend container deployments.
2. **Single-Worker Ingestion Runner**:
   - Background tasks run inside FastAPI's event loop via Python threads. Ingestions do not distribute across multiple machines.
3. **No Authentication / RBAC**:
   - User identity, tokens, and multi-tenant authorization are deliberately excluded from Phase 12 per specifications (scheduled for subsequent phases).

### Phase 17 Distributed Scaling Roadmap
When scaling beyond a single container node:
- **Redis Pub/Sub EventBus**: Replace in-process `IngestionEventBus` with a Redis Pub/Sub channel so SSE clients connected to any FastAPI replica receive real-time ingestion events.
- **Celery / ARQ Distributed Workers**: Move heavy ingestion (PDF OCR, Whisper audio transcription, large web crawls) to dedicated worker pools.
- **Distributed Shared Caches**: Use Redis for retrieval and LLM prompt caching across multiple API instances.

---

## 12. Reproducibility & Deployment Instructions

To deploy the entire Multi-Source RAG Platform on a clean host:

```bash
# 1. Clone the repository
git clone <repository_url>
cd youtube-website-rag-chatbot-main

# 2. Configure environment variables
cp .env.example .env
# Edit .env and insert your GROQ_API_KEY

# 3. Build and launch containers
docker compose build
docker compose up -d

# 4. Verify service health
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost/healthz

# 5. Access the application
# Frontend UI: http://localhost
# Backend API: http://localhost:8000/docs
```
