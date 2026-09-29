# Project Audit: YouTube / Website RAG Chatbot

**Audit Date:** 2026-09-29  
**Auditor:** Antigravity AI Engineering Architecture Team  
**Scope:** Complete repository inspection (`app.py`, `requirements.txt`, `README.md`, `.devcontainer`, `.gitignore`, configuration, security, pipeline)

---

## 1. Existing Architecture & Pipeline Flow

The existing application is a monolithic Streamlit script (`app.py`) providing basic web page and YouTube video ingestion, summarization, and vector search QA.

```text
[User Input URL]
       │
       ▼
[Content Extraction]
   ├── YouTube: langchain_community.document_loaders.YoutubeLoader
   └── Web:     langchain_community.document_loaders.WebBaseLoader
       │
       ▼
[Truncated Summary] (First 5,000 characters sent to ChatGroq llama-3.3-70b-versatile)
       │
       ▼
[Chunking] (RecursiveCharacterTextSplitter: chunk_size=1000, chunk_overlap=200)
       │
       ▼
[Embeddings] (HuggingFaceEmbeddings: sentence-transformers/all-MiniLM-L6-v2)
       │
       ▼
[Vector Store] (FAISS in-memory index created per session)
       │
       ▼
[Retriever] (vectorstore.as_retriever, k=5, standard cosine similarity)
       │
       ▼
[QA Generation] (ChatPromptTemplate + ChatGroq, ungrounded single-shot question answering)
       │
       ▼
[Streamlit Output] (Plain text response in st.write, debug chunks printed directly)
```

---

## 2. Existing Features

| Feature | Implementation | Current Status |
| :--- | :--- | :--- |
| **Website Loader** | `WebBaseLoader` | Functional for static HTML; fails on dynamic JS/paywalled sites. |
| **YouTube Transcript Loader** | `YoutubeLoader.from_youtube_url(language=["en"])` | Functional for English videos with transcripts; fails on auto-captions/languages other than English. |
| **Content Summarizer** | Direct prompt with `[:5000]` character slicing | Working, but naive truncation loses all content after 5,000 chars. |
| **Text Chunking** | `RecursiveCharacterTextSplitter` | Working with fixed 1000/200 params; ignores document structure. |
| **Local Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` | Working locally on CPU; no embedding provider abstraction. |
| **Vector Store** | In-memory `FAISS` | Ephemeral; destroyed on session disconnect or app rerun. |
| **LLM Inference** | `ChatGroq` (`llama-3.3-70b-versatile`) | Fast inference via Groq; hardcoded model and zero fallback. |
| **UI** | Streamlit | Minimal form inputs; not suitable for production multi-tenant SaaS. |

---

## 3. Existing Problems & Deficiencies

### A. Architectural & Scalability Problems
* **Monolithic Script:** Business logic, data extraction, embedding generation, LLM calls, and UI rendering are tightly coupled in a single 229-line script (`app.py`).
* **No Client-Server Separation:** Cannot be consumed by mobile apps, frontend SPAs, or microservices without tearing apart Streamlit.
* **Single-Source Only:** Can only process one URL at a time. Multi-document workspaces are unsupported.
* **Synchronous Blocking Execution:** URL loading, chunking, and embedding generation block the main UI thread. Long documents freeze the UI.
* **Ephemeral In-Memory State:** Vector indexes are stored in `st.session_state`. When the tab closes or server restarts, all ingested data and embeddings are permanently lost.

### B. RAG Quality & Retrieval Problems
* **No Metadata Preservation:** Ingestion strips page numbers, headings, section titles, and YouTube timestamps.
* **No Citations or Source Attribution:** The LLM produces raw answers without citing exact document references, page numbers, or video timestamps.
* **No Conversational Query Rewriting:** Questions like *"Explain that concept further"* fail because the retriever searches literally for *"Explain that concept further"*.
* **No Hybrid Retrieval or Reranking:** Pure dense vector retrieval (k=5) without keyword/BM25 matching or cross-encoder reranking leads to low precision on specific terminology.
* **Naive Truncation in Summarization:** Slicing at `content[:5000]` discards 90%+ of long documents or hour-long lectures.

### C. Hallucination Risks
* **Permissive Prompting:** The prompt `Use the context below to answer the question` does not enforce strict grounding or forbid extrapolation.
* **No Fallback Behavior:** If retrieved chunks lack the answer, the model guesses or uses internal training weights rather than admitting insufficient context.

### D. Security & Vulnerability Concerns
* **SSRF (Server-Side Request Forgery):** `WebBaseLoader(url)` executes raw requests from the host server. An attacker can supply `http://169.254.169.254/latest/meta-data/` or internal network IPs (`http://192.168.1.1`).
* **Raw Error Leakage:** `st.error(f"Failed to load content: {str(e)}")` exposes internal paths, stack traces, and library details.
* **No Authentication / Authorization:** Zero tenant isolation, no user authentication, and no workspace boundary enforcement.
* **No Rate Limiting:** Susceptible to abuse that exhausts Groq API quotas or overwhelms CPU embedding generation.

### E. Persistence & Data Modeling Gaps
* No relational database (PostgreSQL/SQLite).
* No user accounts, workspace entities, document registry, chunk registry, or chat history tables.
* Chat messages are not saved.

### F. Testing & Deployment Readiness Gaps
* Zero unit tests, integration tests, or RAG evaluation metrics.
* `requirements.txt` contains heavy unpinned dependencies (`torch`, `torchvision`) requiring gigabytes of download and complex compilation on constrained servers.
* No `Dockerfile` or `docker-compose.yml` for multi-service orchestration (only a basic devcontainer).

---

## 4. Reusable Components

The following conceptual foundations and libraries from the original project will be preserved and elevated into clean, modular interfaces:

1. **Groq LLM Integration (`ChatGroq`):**
   * Reused in an abstract `LLMProvider` interface (`GroqProvider`), maintaining fast latency and cost efficiency with `llama-3.3-70b-versatile`.
2. **HuggingFace Embeddings (`sentence-transformers/all-MiniLM-L6-v2`):**
   * Reused in an `EmbeddingProvider` interface (`HuggingFaceEmbeddingProvider`), while adding support for OpenAI and Ollama.
3. **FAISS Vector Store Foundations:**
   * Reused in a persistent `VectorStore` adapter (`FAISSVectorStore`) with disk serialization and metadata indexing, while abstracting for Qdrant/pgvector.
4. **YouTube & Web Ingestion Concepts:**
   * Reusable extraction patterns upgraded to dedicated, robust loaders: `YouTubeLoader` (capturing timestamps and video metadata) and `WebLoader` (with Trafilatura/BeautifulSoup cleaning, metadata extraction, and SSRF validation).

---

## 5. Components That Need Refactoring

| Component | Current State | Required Target State |
| :--- | :--- | :--- |
| **Architecture** | Single `app.py` script | Decoupled FastAPI backend (`/backend`) + React/Vite/TS frontend (`/frontend`). |
| **Ingestion Pipeline** | Ad-hoc `load_content` conditional | Extensible adapter-based `BaseLoader` pattern supporting PDF, DOCX, TXT, MD, CSV, XLSX, Web, and YouTube. |
| **Metadata Tracking** | Minimal/discarded | Granular chunk metadata (doc ID, workspace ID, page numbers, timestamps, section titles). |
| **Retrieval Engine** | Naive `k=5` FAISS search | Multi-stage retrieval: Query Rewriter -> Semantic Search + Metadata Filtering -> Reranking -> Strict Grounded Prompting with Citations. |
| **Chat Memory** | None (single turn) | Persistent multi-session conversation with Postgres/SQLite relational storage and streaming tokens (SSE). |
| **UI** | Basic Streamlit widgets | Modern SaaS interface with dark/light mode, workspace switcher, drag-and-drop file uploader, real-time ingestion progress, and interactive citations. |
| **Configuration** | Loose `load_dotenv` calls | Typed Pydantic Settings with validated `.env` configuration. |
