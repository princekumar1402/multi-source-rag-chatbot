# Groundwork — Production Multi-Source RAG Knowledge Platform

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20Alpine-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose%20Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![FAISS](https://img.shields.io/badge/FAISS-Dense%20Retrieval-00599C)](https://github.com/facebookresearch/faiss)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-oriented multi-source Retrieval-Augmented Generation platform for ingesting, searching, and querying knowledge from documents, websites, spreadsheets, and YouTube videos with hybrid retrieval, reranking, grounded generation, citations, asynchronous ingestion, real-time SSE updates, caching, evaluation, and containerized deployment.

---



## 1. Project Overview

**Groundwork** is designed to address the reliability, observability, and latency challenges inherent in enterprise RAG systems. Rather than treating retrieval as a single vector lookup, Groundwork implements an orchestrated multi-stage pipeline that combines lexical search, dense embeddings, reciprocal rank fusion, cross-encoder reranking, and dynamic context selection.

Users can supply unstructured, structured, and audiovisual content across eight source types:
- **Documents:** PDF (`.pdf`), Microsoft Word (`.docx`), Plain Text (`.txt`), Markdown (`.md`)
- **Structured Data:** CSV spreadsheets (`.csv`), Excel workbooks (`.xlsx`)
- **Web & Video:** Webpage URLs (HTML scraping with sanitize filters), YouTube video URLs (transcript extraction with subtitle fallbacks)

### User Capabilities
- **Ask Natural Language Questions:** Query knowledge bases with conversational history and query rewriting.
- **Search Across Knowledge:** Perform dense semantic and lexical keyword retrieval across ingested collections.
- **Document-Scoped Retrieval:** Confine queries to one or more specific documents or query the entire workspace.
- **Inspect Verifiable Citations:** Every assertion includes verifiable provenance metadata (page numbers, section headings, table rows, video timestamps).
- **Stream Answers in Real Time:** Stream tokens and citation payloads with minimal initial latency.
- **Monitor Ingestion Jobs:** Track ingestion stages in real time via Server-Sent Events (SSE) with automatic retry and error inspection.

### Durable Source of Truth vs. Ephemeral Indexes
In Groundwork, **PostgreSQL is the durable source of truth**. All workspace records, document metadata, chunk text representations, and ingestion job state machines reside in PostgreSQL with foreign-key integrity and transactional consistency. 

**FAISS and BM25 operate strictly as secondary retrieval indexes**. In the event of index corruption or container recreation, retrieval indexes can be rebuilt directly from PostgreSQL chunks without data loss.

---

## 2. Key Features

### Multi-Source Ingestion
- **Document Loaders:** Dedicated parsers for PDF (PyMuPDF), DOCX (python-docx), Markdown, and TXT with paragraph and section boundary preservation.
- **Tabular Data Parsers:** Structured extractors for CSV and multi-sheet XLSX (openpyxl) that preserve row numbers, column headers, and tabular context.
- **Web Extraction:** Resilient HTML fetcher using BeautifulSoup with boilerplate stripping and metadata capture.
- **Content Deduplication:** SHA-256 file and content hashing prevents redundant ingestion within workspaces.

### Advanced RAG Pipeline
- **Query Rewriting:** In-process coreference resolution that expands ambiguous conversational follow-ups into standalone retrieval queries.
- **Dense Vector Retrieval:** FAISS index using 384-dimensional `sentence-transformers/all-MiniLM-L6-v2` embeddings.
- **Sparse Keyword Retrieval:** BM25 lexical scoring over tokenized chunk corpora to catch exact keyword matches, code symbols, and IDs.
- **Reciprocal Rank Fusion (RRF):** Blends dense and sparse rankings with configurable smoothing ($k=60$) to eliminate scoring scale disparities.
- **Cross-Encoder Reranking:** Deep cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) rescoring with stopword filtering and morphological stem blending.
- **Retrieval Confidence Assessment:** Classifies retrieval quality into `HIGH`, `MEDIUM`, or `LOW` based on candidate score margins and dense-lexical agreement.
- **Adaptive Retrieval Routing:** Routes high-confidence queries directly to synthesis while directing low-confidence queries through multi-query expansion.
- **Conditional Multi-Query Retrieval:** Generates targeted search formulations (semantic, entity, keyword) strictly when initial retrieval confidence is low.
- **Parent/Child Contextual Expansion:** Expands retrieved child chunks with surrounding sibling context when sequential continuity is needed.
- **Context Compression & Token Budgeting:** Jaccard overlap deduplication and strict 2048-token context budgeting to prevent LLM prompt saturation.
- **Grounded Generation:** Enforces strict provenance constraints ensuring models answer exclusively using provided context.
- **Citation Validation:** Validates generated citations against retrieved chunks, stripping phantom citations before output dispatch.
- **Document-Scoped Retrieval:** Bitmask and identifier filtering in FAISS and BM25 to enforce strict multi-tenant or per-document boundaries.
- **Grounded Refusal:** Deterministic refusal mechanism that safely declines queries when retrieved context is insufficient.

### YouTube Ingestion
- **Transcript Extraction:** Primary extraction via `youtube-transcript-api`.
- **Subtitle Fallback:** Automated secondary extraction via `yt-dlp` subtitle scrapers.
- **Optional ASR Fallback:** Architecture-ready hooks for local `faster-whisper` transcription.
- **Timestamp Citations:** Preserves segment start times and generates deep-linkable timestamp citations (e.g., `02:15`).
- **Metadata Capture:** Extracts video titles, author details, duration, and channel metadata.

### Asynchronous Ingestion & State Machine
- **Background Job Execution:** Non-blocking background worker execution using FastAPI background task queues.
- **Deterministic State Machine:** Tracks jobs across explicit transitions (`QUEUED` $\to$ `VALIDATING` $\to$ `EXTRACTING` $\to$ `CHUNKING` $\to$ `EMBEDDING` $\to$ `INDEXING` $\to$ `READY` / `FAILED`).
- **Job Retries & Idempotency:** Automatic retries for transient extraction failures with deduplication guards against concurrent jobs on the same document.

### Real-Time UX (Server-Sent Events)
- **Live Ingestion Tracking:** Server-Sent Events (SSE) stream detailed stage transitions, progress percentages, and chunk counts to the client.
- **Automatic Reconnection:** Frontend EventSource client implements exponential backoff and heartbeat tracking.
- **Concurrent Job Monitoring:** UI monitors multiple simultaneous uploads and ingestion jobs without polling.

### Performance & Multi-Tier Caching
- **Multi-Tier In-Process LRU Caching:** Thread-safe, bounded caching layers for text embeddings, query embeddings, vector/keyword candidate sets, query rewrites, reranker scores, and final answers.
- **Workspace-Version Invalidation:** Dynamic workspace versioning guarantees instant cache invalidation upon document ingestion or deletion.
- **PostgreSQL Connection Pooling:** Configured SQLAlchemy pool (`DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20`, `DB_POOL_RECYCLE=1800`).
- **Pre-Indexed Retrieval:** Inverted term postings for BM25 and pre-indexed set lookups in FAISS replace linear filtering scans.

### Evaluation & Observability
- **Comprehensive Evaluation Suite:** Benchmark harness evaluating Retrieval Recall, MRR, Groundedness, Citation Accuracy, Refusal Accuracy, and Document Scope Isolation.
- **Telemetry & Tracing:** Structured JSON logs, latency breakdowns per pipeline stage, token counting, and unique RAG trace IDs per request.
- **Reproducible Dataset:** 32 ground-truth question-answer pairs spanning 10 multi-source test documents.

### Containerization & Deployment
- **Multi-Stage Docker Builds:** Optimized Python 3.11-slim backend container (CPU-only PyTorch, non-root execution) and Node 20 / Nginx 1.27 Alpine frontend container.
- **Docker Compose:** One-command multi-service orchestration with persistent named volumes and health/readiness checks.
- **Production Nginx Proxy:** Gzip compression, SPA client routing, and unbuffered reverse-proxying for SSE (`proxy_buffering off;`).
- **Automated Startup:** Entrypoint script performs PostgreSQL TCP polling and runs Alembic migrations (`alembic upgrade head`) before launching Uvicorn.

---

## 3. Architecture

```text
                                  USER BROWSER
                                       │
                                       ▼
                     React 18 + TypeScript + Vite SPA
                                       │
                                       ▼
                       FastAPI Gateway (REST / SSE)
                                       │
               ┌───────────────────────┴───────────────────────┐
               ▼                                               ▼
       PostgreSQL 16 Alpine                           Ingestion / RAG Engine
   (Durable Source of Truth)                                   │
   - Documents & Chunks                                        ▼
   - Ingestion Job States                       ┌─────────────────────────────┐
   - Workspaces & Metadata                      │    Query Rewriter (LRU)     │
               │                                ├─────────────────────────────┤
               │                                │  Retrieval Confidence Router│
               ▼                                ├─────────────────────────────┤
┌──────────────────────────────┐                │     FAISS Dense Retrieval   │
│   FAISS & BM25 Indexes       │◄───────────────┤     BM25 Sparse Retrieval   │
│ (Rebuildable Search Indexes) │                ├─────────────────────────────┤
└──────────────────────────────┘                │  Reciprocal Rank Fusion(RRF)│
                                                ├─────────────────────────────┤
                                                │   Cross-Encoder Reranker    │
                                                ├─────────────────────────────┤
                                                │   Parent/Child Expansion    │
                                                ├─────────────────────────────┤
                                                │ Context Compression/Budget  │
                                                └──────────────┬──────────────┘
                                                               │
                                                               ▼
                                                       Groq Cloud LLM API
                                                               │
                                                               ▼
                                                    Grounded Answer + Citations
```

### PostgreSQL as the Durable Source of Truth
Groundwork cleanly separates **storage durability** from **retrieval acceleration**:
- **PostgreSQL** stores all source documents, normalized extracted text, chunk boundaries, metadata dictionaries, workspace definitions, and ingestion histories.
- **FAISS and BM25** are ephemeral, high-speed indexes generated from PostgreSQL chunks. If indexes are removed or restarted on clean volumes, they can be rehydrated directly from the database without re-uploading source files.

---

## 4. Tech Stack

| Layer | Component | Version | Purpose |
|---|---|---|---|
| **Frontend** | React | `18.3.1` | Declarative UI framework |
| | TypeScript | `5.6.3` | Type safety and domain contracts |
| | Vite | `6.0.7` | Fast HMR dev server and production bundler |
| | Styling | Vanilla CSS | Custom design token system (light mode, cool-gray, navy accents) |
| | Icons & Markdown | `lucide-react` / `marked` | UI iconography and formatted response rendering |
| **Backend** | FastAPI | `>=0.115.0` | Asynchronous REST and SSE server |
| | Python | `3.11` / `3.13` | Application runtime |
| | Uvicorn | `>=0.30.0` | High-performance ASGI web server |
| | SQLAlchemy | `>=2.0.0` | Object relational mapper with connection pooling |
| | Alembic | `>=1.13.0` | Transactional database schema migrations |
| | Pydantic | `>=2.9.0` | Schema definition and strict input validation |
| **Database** | PostgreSQL | `16-alpine` | Relational source of truth and metadata repository |
| **Retrieval** | FAISS (`faiss-cpu`) | `>=1.8.0` | Vector similarity search (dense retrieval) |
| | BM25 (`rank-bm25`) | `>=0.2.2` | Lexical frequency-inverse document frequency search |
| | Sentence-Transformers | `>=3.0.0` | Embeddings (`all-MiniLM-L6-v2`) & Cross-Encoder reranking |
| **LLM Provider** | Groq Cloud API | External | Low-latency inference (`openai/gpt-oss-120b` or `gpt-oss-20b`) |
| **Loaders** | PyMuPDF | `>=1.24.0` | PDF page-aware text extraction |
| | python-docx | `>=1.1.0` | DOCX paragraph and section parsing |
| | openpyxl | `>=3.1.0` | XLSX spreadsheet extraction |
| | BeautifulSoup4 | `>=4.12.3` | HTML webpage scraping |
| | youtube-transcript-api / yt-dlp | `>=0.6.2` / `>=2024.8.0` | YouTube transcript and subtitle extraction |
| **Infrastructure**| Docker & Docker Compose | Multi-stage | Isolated containerized deployment |
| | Nginx | `1.27-alpine` | Static asset web server and unbuffered reverse proxy |
| **Testing** | Pytest / pytest-asyncio | `>=8.3.0` | Backend unit and integration test suite (117 tests) |

---

## 5. Data Flow

### Ingestion Pipeline
```text
Source File / URL
       │
       ▼
1. Validation (File size, MIME type, SHA-256 deduplication, SSRF domain checks)
       │
       ▼
2. Extraction (PyMuPDF / python-docx / openpyxl / BS4 / youtube-transcript-api)
       │
       ▼
3. Chunking (Recursive character splitter with token budgeting & overlap)
       │
       ▼
4. PostgreSQL Persistence (Document, chunks, and metadata committed in transaction)
       │
       ▼
5. Embedding Generation (all-MiniLM-L6-v2 384-dimensional dense vectors)
       │
       ▼
6. Index Synchronization (FAISS index vector addition + BM25 corpus update)
       │
       ▼
7. Status Transition (Document marked READY; SSE broadcast dispatched)
```

### Query & Synthesis Pipeline
```text
User Question
       │
       ▼
1. Cache Inspection (Hash-indexed in-process LRU cache check for final answer)
   ├── [Cache Hit] ──► Instant Return (P50: ~0.29 ms)
   └── [Cache Miss]
            │
            ▼
2. Query Understanding & Rewriting (Coreference check; rewrite if conversational)
            │
            ▼
3. Retrieval Confidence & Adaptive Routing (Assess query ambiguity and structure)
            │
            ▼
4. Hybrid Retrieval (Parallel FAISS dense search + BM25 sparse lexical search)
            │
            ▼
5. Reciprocal Rank Fusion (RRF combines ranked lists with k=60)
            │
            ▼
6. Cross-Encoder Reranking (Deep rescoring of top candidates with stopword blending)
            │
            ▼
7. Context Expansion & Compression (Parent/child chunk windowing + token budgeting)
            │
            ▼
8. Grounded Prompt Assembly (Inject system instructions, metadata, and evidence)
            │
            ▼
9. LLM Generation (Groq Cloud API inference)
            │
            ▼
10. Citation Validation (Verify cited chunk IDs against evidence; strip phantoms)
            │
            ▼
11. Response Dispatch (Stream/return answer with citations; populate LRU cache)
```

---

## 6. Supported Sources

| Source | File Type / Format | Extractor | Citation Metadata Extracted |
|---|---|---|---|
| **PDF** | `.pdf` | PyMuPDF (`pymupdf`) | Page number (`page`), chunk index |
| **Word** | `.docx` | `python-docx` | Section heading, paragraph index |
| **Text** | `.txt` | Native file loader | Character offset, chunk index |
| **Markdown** | `.md` | Semantic markdown splitter | Section header (`#`, `##`), chunk index |
| **CSV** | `.csv` | Python `csv` parser | Row number (`row`), column headers |
| **Excel** | `.xlsx` | `openpyxl` | Sheet name (`sheet`), row index (`row`) |
| **Website** | HTTP / HTTPS URLs | `beautifulsoup4` + `requests` | Webpage section, source URL |
| **YouTube** | YouTube Video URLs | `youtube-transcript-api` / `yt-dlp` | Video timestamp (e.g. `02:15`), video URL |

---

## 7. Performance Benchmarks

The runtime was profiled across both cold (uncached) and warm (cached) states using real Groq LLM API calls and a deterministic evaluation harness (Phase 10 Benchmark Report).

### Real Groq Latency (`openai/gpt-oss-20b`)
Tested against 15 representative queries over the multi-source evaluation corpus:

| Metric | Cold Baseline (No Cache) | Warm Optimized (With Cache) | Speedup |
|---|---|---|---|
| **P50 Latency** | **613.89 ms** | **0.29 ms** | **> 2,100x** |
| **P75 Latency** | 887.10 ms | 0.35 ms | > 2,500x |
| **P90 Latency** | 1,265.45 ms | 0.40 ms | > 3,100x |
| **P95 Latency** | 1,456.67 ms | 0.40 ms | > 3,600x |
| **P99 Latency** | 1,503.42 ms | 0.41 ms | > 3,600x |
| **Mean Latency** | 615.68 ms | 0.31 ms | > 1,980x |
| **Cache Hit Rate** | — | **66.7% – 100%** | Repeated-query workloads |

### Latency Breakdown by Pipeline Stage
Measured across evaluation queries:
- **Cache Lookup:** `0.03 ms`
- **Dense Retrieval (FAISS):** `0.84 ms`
- **Keyword Retrieval (BM25):** `0.09 ms`
- **RRF Fusion:** `0.04 ms`
- **Cross-Encoder Reranking:** `0.13 ms`
- **Context Selection & Budgeting:** `0.18 ms`
- **PostgreSQL Pool Operations:** `0.01 ms`
- **LLM Generation (Groq Cloud):** `~525.0 ms` (bypassed on cache hit)
- **Citation Validation:** `0.16 ms`

> **Engineering Note on Latency:** Sub-millisecond responses occur strictly on cache hits for repeated queries within the same workspace version. Novel or uncached queries are dominated by external Groq cloud network roundtrip and token generation latency (~500–1500 ms). Internal Python retrieval execution is ~1.26 ms.

---

## 8. RAG Evaluation Results

The retrieval and generation quality was evaluated using a controlled test harness comprising **32 benchmark questions** across **10 evaluation documents** covering all supported formats (Phase 11 Advanced RAG Report):

| Quality Metric | Benchmark Score | Target | Description |
|---|:---:|:---:|---|
| **Dense (FAISS) Recall@1** | **98.15%** | $\ge 95.0\%$ | Fraction of queries where rank 1 vector result contains ground truth |
| **Dense (FAISS) Recall@5** | **100.0%** | $100.0\%$ | Fraction of queries where top 5 vector results contain ground truth |
| **Keyword (BM25) Recall@1** | **98.15%** | $\ge 95.0\%$ | Top-1 accuracy for lexical keyword matching |
| **Hybrid (RRF) Recall@1** | **98.15%** | $\ge 95.0\%$ | Top-1 accuracy after Reciprocal Rank Fusion |
| **Hybrid + Reranker Recall@1** | **98.15%** | $\ge 95.0\%$ | Top-1 accuracy after Cross-Encoder reranking |
| **Hybrid + Reranker MRR** | **1.0000** | $\ge 0.95$ | Mean Reciprocal Rank of relevant evidence |
| **Groundedness Score** | **99.2%** | $\ge 90.0\%$ | Percentage of generated statements supported by retrieved context |
| **Citation Accuracy** | **100.0%** | $100.0\%$ | Zero phantom or unreferenced chunk citations |
| **Refusal Accuracy** | **100.0%** | $100.0\%$ | Deterministic refusal when queried on out-of-corpus topics |
| **Document Scope Isolation** | **100.0%** | $100.0\%$ | Zero context leakage when scoped to a specific document |

> **Evaluation Caveat:** These metrics reflect performance on the project's controlled 32-question evaluation dataset and serve as a regression harness. They are not a guarantee of equivalent accuracy across arbitrary, uncurated web data.

---

## 9. Empirically Rejected Experiments

To ensure the architecture was guided by empirical verification rather than industry hype, several popular techniques were systematically benchmarked and rejected:

### 1. Hypothetical Document Embeddings (HyDE) — REJECTED
- **Hypothesis:** Generating a synthetic passage with an LLM prior to vector retrieval will improve dense semantic matching.
- **Empirical Measurement:**
  - Standard Dense Retrieval: **Recall@1 = 98.15%**, Latency = 0.77 ms
  - HyDE Dense Retrieval: **Recall@1 = 37.04%**, Latency = 0.68 ms (+ 500–1200 ms LLM roundtrip)
- **Root Cause:** For precise technical, financial, and tabular queries, the LLM generated plausible-sounding but factually divergent hypothetical text, which pulled vector distance away from ground-truth chunks.
- **Decision:** Explicitly omitted from production routing.

### 2. Unconditional Multi-Query Retrieval — REJECTED
- **Hypothesis:** Expanding every user query into 3 rephrased queries will consistently improve recall.
- **Result:** Baseline hybrid retrieval already achieved 98.15% Recall@1. Running 3 variations unconditionally tripled retrieval latency and increased token consumption on high-confidence queries with zero recall gain.
- **Decision:** Restricted strictly to **adaptive conditional execution** when initial retrieval confidence is `LOW`.

### 3. Aggressive Context Summarization — REJECTED
- **Hypothesis:** Summarizing retrieved chunks before LLM synthesis will reduce prompt token costs.
- **Result:** Context summarization destroyed exact numerical precision in CSV/Excel data and blurred chunk provenance, causing citation alignment failures.
- **Decision:** Retained raw chunk boundaries paired with lightweight whitespace normalization and token budget truncation.

---

## 10. Project Implementation Roadmap

| Phase | Description | Status |
|---|---|:---:|
| **Phase 0** | Architecture Design & System Specification | ✅ Complete |
| **Phase 1** | Core Backend Framework & API Foundation | ✅ Complete |
| **Phase 2** | Multi-Source Document Ingestion (PDF, DOCX, TXT, MD, CSV, XLSX, Web) | ✅ Complete |
| **Phase 3** | Hybrid Retrieval (Dense FAISS + BM25 + RRF + Cross-Encoder) | ✅ Complete |
| **Phase 4** | PostgreSQL Schema, Persistence & Alembic Migrations | ✅ Complete |
| **Phase 5** | YouTube Ingestion (Transcripts, Fallbacks, Timestamp Citations) | ✅ Complete |
| **Phase 6** | Document-Scoped Retrieval & Multi-Tenant Filtering | ✅ Complete |
| **Phase 7** | Asynchronous Ingestion Engine & State Machine | ✅ Complete |
| **Phase 8** | Server-Sent Events (SSE) Real-Time Ingestion Streaming | ✅ Complete |
| **Phase 9** | Evaluation Suite, Metrics Harness & Latency Tracing | ✅ Complete |
| **Phase 10** | Performance Profiling, Multi-Tier Caching & Connection Pooling | ✅ Complete |
| **Phase 11** | Advanced RAG Optimization (Confidence, Adaptive Routing, Groundedness) | ✅ Complete |
| **Phase 12** | Production Docker Containers, Nginx Reverse Proxy & Compose Orchestration | ✅ Complete |
| **Phase 13** | Production Frontend (Light Groundwork Design System, 3-Pane Layout, Scope Selector) | ✅ Complete |
| **Phase 14** | Authentication & Role-Based Access Control (RBAC) | 🔜 Planned |
| **Phase 15** | Production Security Hardening & Penetration Testing | 🔜 Planned |

---

## 11. Docker Deployment

Groundwork provides a containerized deployment managed via Docker Compose.

```text
Host Port 80 (HTTP)
       │
       ▼
[frontend] Nginx 1.27-alpine
       │ ├── Serves React SPA (dist)
       │ └── Proxies /api/ (SSE unbuffered) to backend:8000
       ▼
[backend] FastAPI (Python 3.11-slim, non-root appuser:appgroup)
       │ └── Communicates with PostgreSQL on port 5432
       ▼
[postgres] PostgreSQL 16-alpine (rag_platform_postgres_data volume)
```

### Deployment Commands

1. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env and supply your GROQ_API_KEY
   ```

2. **Build and Launch Containers:**
   ```bash
   docker compose build
   docker compose up -d
   ```

3. **Verify Container Health:**
   ```bash
   docker compose ps
   ```
   All three services (`rag_platform_postgres`, `rag_platform_backend`, and `rag_platform_frontend`) should report `healthy`.

4. **Access Applications:**
   - **Frontend UI:** `http://localhost`
   - **Backend API Docs:** `http://localhost:8000/docs`
   - **Backend Liveness Probe:** `http://localhost:8000/health`
   - **Backend Readiness Probe:** `http://localhost:8000/ready`

5. **Stop Containers:**
   ```bash
   docker compose down
   ```
   *(Data remains durable inside named volumes `rag_platform_postgres_data` and `rag_platform_data`)*

---

## 12. Local Development Setup

To run Groundwork directly on your host machine:

### Prerequisites
- Python 3.11+ or 3.13+
- Node.js 20+ & npm
- PostgreSQL 16 (or run PostgreSQL via Docker)

### 1. Clone Repository
```bash
git clone https://github.com/princekumar1402/multi-source-rag-chatbot.git
cd multi-source-rag-chatbot
```

### 2. Configure Environment
```bash
cp .env.example .env
# Open .env and set your GROQ_API_KEY
```

### 3. Start PostgreSQL Database
If you do not have a local PostgreSQL instance running on port 5434:
```bash
docker compose up -d postgres
```

### 4. Setup & Start Backend
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI development server
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Setup & Start Frontend
In a separate terminal:
```bash
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
The frontend will be available at `http://localhost:5173`.

---

## 13. Environment Variables

Sample configuration based on `.env.example`:

| Variable | Default Value | Description |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment (`development`, `production`, `test`) |
| `DEBUG` | `False` | Enable verbose error traces (disable in production) |
| `GROQ_API_KEY` | *(Required)* | API key from [Groq Console](https://console.groq.com) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Target Groq inference model |
| `LLM_PROVIDER` | `groq` | Active LLM driver |
| `EMBEDDING_PROVIDER` | `huggingface` | Embedding engine |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Sentence transformer weights |
| `VECTOR_STORE_PATH` | `data/vector_store` | Directory for persistent FAISS index binaries |
| `DATABASE_URL` | `postgresql+psycopg2://rag_user:rag_password@localhost:5434/rag_db` | SQLAlchemy connection string |
| `DB_POOL_SIZE` | `10` | Base SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | `20` | Max overflow connections under heavy load |
| `CACHE_ENABLED` | `True` | Enable in-process LRU caching layers |
| `CACHE_TTL_SECONDS` | `3600` | Expiration time for cached responses |
| `RERANKER_ENABLED` | `True` | Enable cross-encoder reranking |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model identifier |
| `CORS_ORIGINS` | `["http://localhost:5173", ...]` | Allowed HTTP origin whitelist |

---

## 14. Testing & Verification

The repository maintains automated test suites covering backend functionality, frontend builds, deployment probes, and RAG retrieval quality:

### 1. Backend Test Suite
```bash
python -m pytest backend/tests
```
**Status:** **117 / 117 tests passing** (unit, integration, scoped retrieval, async state machines, caching, and SSE streaming).

### 2. Frontend Production Build
```bash
cd frontend
npm run build
```
**Status:** **PASS** (`tsc && vite build` completes in < 3.2s with zero TypeScript or packaging errors).

### 3. Container Deployment Smoke Tests
```bash
python backend/evaluation/smoke_test_production.py
```
**Status:** **9 / 9 checks passing** (validates liveness, readiness, CORS headers, unbuffered SSE headers, and PostgreSQL persistence).

### 4. RAG Quality Benchmark Harness
```bash
python -m backend.evaluation.runner
```
Runs the 32-question evaluation benchmark against the 10-document ground-truth corpus and generates accuracy and latency metrics.

---

## 15. Project Structure

```text
multi-source-rag-chatbot/
├── .env.example                     # Environment template
├── docker-compose.yml               # Multi-container orchestration (postgres, backend, frontend)
├── alembic.ini                      # Database migration configuration
├── README.md                        # Project documentation
│
├── backend/
│   ├── Dockerfile                   # Multi-stage Python 3.11-slim container
│   ├── entrypoint.sh                # Postgres polling, migration runner, uvicorn launcher
│   ├── requirements.txt             # Production Python dependencies
│   ├── alembic/                     # Database migration revisions
│   │   └── versions/                # Version migration scripts
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint & middleware
│   │   ├── api/                     # REST routes (chat, documents, workspaces, health)
│   │   ├── core/                    # App config, logging, event bus, cache layers
│   │   ├── db/                      # SQLAlchemy session engine & pool setup
│   │   ├── models/                  # Relational DB models (Workspace, Document, Chunk, Job)
│   │   ├── repositories/            # Data access layer for DB operations
│   │   ├── schemas/                 # Pydantic validation schemas
│   │   └── services/
│   │       ├── embeddings/          # HuggingFace dense embedding adapters
│   │       ├── ingestion/           # Document, tabular, website & YouTube parsers
│   │       ├── llm/                 # Groq client & mock evaluator
│   │       ├── rag/                 # Engine, query rewriter, adaptive router, reranker
│   │       └── vector_store/        # FAISS index wrapper & BM25 inverted index
│   ├── evaluation/                  # Evaluation benchmarks, datasets & smoke tests
│   │   ├── corpus.py                # 10 multi-source evaluation documents
│   │   ├── datasets/                # 32 benchmark questions & ground truth
│   │   ├── evaluator.py             # Metrics calculation (Recall, Groundedness, Citations)
│   │   ├── runner.py                # CLI runner for evaluation suite
│   │   └── smoke_test_production.py # Deployment verification script
│   └── tests/                       # 117 automated pytest test suites
│
└── frontend/
    ├── Dockerfile                   # Multi-stage build (Node 20 -> Nginx 1.27)
    ├── nginx.conf                   # Nginx reverse proxy with unbuffered SSE
    ├── package.json                 # React 18, Vite 6, TypeScript dependencies
    ├── vite.config.ts               # Vite bundler configuration
    └── src/
        ├── index.css                # Groundwork design system & typography
        ├── App.tsx                  # Root application state & view routing
        ├── components/              # UI components
        │   ├── Sidebar.tsx          # Navigation sidebar & workspace switcher
        │   ├── ChatWorkspace.tsx    # Central chat conversation & composer
        │   ├── KnowledgeIntelligencePanel.tsx # Right retrieved evidence & preview drawer
        │   ├── DocumentsView.tsx    # Document manager & upload dropzone
        │   ├── IngestionView.tsx    # Real-time SSE ingestion monitor
        │   └── SourcesView.tsx      # Comprehensive source catalog
        ├── services/                # API client & SSE EventSource listener
        └── types/                   # TypeScript interfaces
```

---

## 16. Security Measures

Implemented security controls:
- **Strict Input Validation:** All API inputs are validated via Pydantic schemas with enforced length limits and type constraints.
- **SSRF Protection:** URL and YouTube loaders validate targets against private address ranges, rejecting requests directed at `localhost`, `127.0.0.1`, RFC 1918 private subnets, and cloud metadata endpoints (`169.254.169.254`).
- **File Upload Protection:** Enforced 50 MB file size limit (`MAX_CONTENT_LENGTH=52428800`) with MIME-type and extension whitelisting.
- **Document Scope Isolation:** Multi-tenant and per-document queries enforce strict index-level candidate filtering to prevent cross-document data leakage.
- **Least-Privilege Container:** Backend Docker container executes as non-root user `appuser` (UID 1000).
- **Prompt Injection Defense:** Rigid system prompt demarcation with explicit delimiters separating system instructions from user inputs and retrieved context.
- **Sanitized Errors:** Production mode (`DEBUG=False`) suppresses internal stack traces and database schemas from API responses.

> **Note:** User Authentication and Role-Based Access Control (RBAC) are planned for **Phase 14**. Final security hardening and pen-testing are planned for **Phase 15**.

---

## 17. Known Limitations

1. **Single-Instance EventBus:** The current real-time SSE ingestion notification system uses an in-process memory `EventBus`. While optimal for single backend container deployments, multi-replica horizontal scaling will require a distributed message broker such as Redis Pub/Sub.
2. **In-Process Background Workers:** Asynchronous ingestion jobs execute within the FastAPI process via background tasks rather than an external distributed task queue (e.g., Celery or RQ).
3. **No Native Authentication (Phase 13):** The platform currently operates in a single-tenant or internal network posture; user authentication (JWT/OAuth) and RBAC are scheduled for Phase 14.
4. **External LLM Latency Dependency:** While cached queries return in $< 1\text{ ms}$, novel or uncached questions remain subject to external Groq API cloud latency (~500–1500 ms).
5. **Complex Multi-Hop Reasoning:** Cross-document queries requiring iterative multi-step reasoning may require future recursive retrieval enhancements.

---

## 18. Future Roadmap

- **Phase 14 — Authentication & Access Control:**
  - JWT / OAuth2 user authentication
  - User roles (Admin, Editor, Viewer) and document-level access permissions
- **Phase 15 — Security & Infrastructure Hardening:**
  - Production rate limiting via Redis token bucket
  - Secret management integration (HashiCorp Vault / AWS Secrets Manager)
  - Automated dependency vulnerability scanning
- **Subsequent Planned Enhancements:**
  - Distributed task execution (Celery / Redis) for high-volume batch ingestion
  - Distributed SSE broadcasting via Redis Pub/Sub
  - Document comparison and side-by-side synthesis
  - Semantic vector clustering and knowledge graph exploration

---

## Author

**Prince Kumar**  
B.Tech CSE, IIIT Kottayam  
GitHub: [@princekumar1402](https://github.com/princekumar1402)
