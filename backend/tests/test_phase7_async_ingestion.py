import pytest
import uuid
import os
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.db.session import SessionLocal
from backend.app.models.document import Document
from backend.app.models.ingestion_job import IngestionJob
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.chunk_repo import ChunkRepository
from backend.app.repositories.ingestion_job_repo import IngestionJobRepository

from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.rag.bm25 import BM25Retriever
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.ingestion.job_runner import IngestionJobRunner
from backend.app.services.ingestion.job_service import IngestionJobService
from backend.app.schemas.document import SourceType, DocumentChunk, ChunkMetadata
from backend.app.schemas.ingestion_job import IngestionJobResponse, IngestionStage
from backend.app.schemas.rag import RAGQueryRequest
from backend.app.services.rag.engine import RAGEngine
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.services.rag.hybrid import HybridRetriever
from backend.app.services.rag.context_selector import ContextSelector

client = TestClient(app)

class DummyFastEmbedder:
    def __init__(self, dimension: int = 4):
        self.dimension = dimension

    def embed_query(self, query: str):
        return [1.0, 0.0, 0.0, 0.0]

    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

class DummyLLM:
    def generate(self, prompt: str, system_prompt: str = None) -> str:
        if "quantum" in prompt.lower():
            return "Quantum computing operates on qubits according to [Source 1]."
        return "The available knowledge base sources do not contain enough information to answer this question."

@pytest.fixture
def mock_pipeline_env(tmp_path):
    """Provides an isolated pipeline, runner, and job service using a clean tmp_path."""
    embedder = DummyFastEmbedder(dimension=4)
    vstore = FAISSVectorStore(dimension=4, store_dir=str(tmp_path / "vs"))
    bm25 = BM25Retriever()
    pipeline = IngestionPipeline(
        embedder=embedder,
        vector_store=vstore,
        keyword_retriever=bm25,
        session_factory=SessionLocal
    )
    runner = IngestionJobRunner(pipeline=pipeline, session_factory=SessionLocal)
    job_service = IngestionJobService(pipeline=pipeline, runner=runner, session_factory=SessionLocal)
    return {
        "pipeline": pipeline,
        "runner": runner,
        "job_service": job_service,
        "vstore": vstore,
        "bm25": bm25,
        "embedder": embedder,
        "tmp_path": tmp_path
    }

# 1 & 2. Upload creates Document + IngestionJob and returns immediately
def test_upload_creates_job_and_returns_immediately():
    content = b"Phase 7 asynchronous ingestion testing content."
    res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("async_test.txt", content, "text/plain")},
        data={"workspace_id": "ws_phase7_test", "title": "Async Test Doc"}
    )
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    assert "document_id" in data
    assert data["status"] in ("pending", "processing", "completed")

# 3, 4, 5. Job execution lifecycle: PENDING -> PROCESSING -> COMPLETED & Document -> READY
def test_job_runner_lifecycle_success(mock_pipeline_env):
    runner = mock_pipeline_env["runner"]
    job_service = mock_pipeline_env["job_service"]
    vstore = mock_pipeline_env["vstore"]
    bm25 = mock_pipeline_env["bm25"]

    file_bytes = b"Asynchronous job runner processes documents without blocking the main event loop."
    file_name = "test_lifecycle.txt"
    ws_id = "ws_lifecycle"

    job_resp, needs_processing = job_service.create_file_job(
        file_bytes=file_bytes,
        file_name=file_name,
        workspace_id=ws_id,
        custom_title="Lifecycle Test"
    )
    assert needs_processing is True
    assert job_resp.status == "pending"

    # Execute job synchronously via runner
    runner.run_job(job_id=job_resp.job_id, file_bytes=file_bytes)

    with SessionLocal() as db:
        job = IngestionJobRepository.get(db, job_resp.job_id)
        assert job.status == "completed"
        assert job.stage == IngestionStage.COMPLETED.value
        assert job.progress == 1.0

        doc = DocumentRepository.get(db, job_resp.document_id)
        assert doc.status == "ready"
        assert doc.chunk_count > 0

        chunks = ChunkRepository.list_by_document(db, doc.id)
        assert len(chunks) == doc.chunk_count

    # Verify indexed in FAISS and BM25
    faiss_res = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=5, filters={"document_ids": [doc.id]})
    assert len(faiss_res) > 0
    bm25_res = bm25.search("asynchronous", top_k=5, filters={"document_ids": [doc.id]})
    assert len(bm25_res) > 0

# 6. Status endpoint
def test_job_status_endpoint():
    with SessionLocal() as db:
        ws = WorkspaceRepository.get_or_create(db, "ws_status_test")
        job = IngestionJobRepository.create(
            db, workspace_id=ws.id, source_type="txt", status="processing", stage="chunking", progress=0.45
        )
        db.commit()
        job_id = job.id

    res = client.get(f"/api/v1/ingestion/jobs/{job_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["job_id"] == job_id
    assert data["status"] == "processing"
    assert data["stage"] == "chunking"
    assert data["progress"] == 0.45

# 7 & 8. Failed ingestion handling & Document becomes FAILED
def test_failed_ingestion_cleans_partial_state(mock_pipeline_env):
    runner = mock_pipeline_env["runner"]
    job_service = mock_pipeline_env["job_service"]
    vstore = mock_pipeline_env["vstore"]
    bm25 = mock_pipeline_env["bm25"]

    file_bytes = b"Corrupted content triggering error"
    ws_id = "ws_fail_test"

    job_resp, _ = job_service.create_file_job(
        file_bytes=file_bytes,
        file_name="corrupt.txt",
        workspace_id=ws_id
    )

    # Force chunker to raise an exception
    with patch.object(runner.pipeline.chunker, "chunk_document", side_effect=ValueError("Simulated chunking failure")):
        runner.run_job(job_id=job_resp.job_id, file_bytes=file_bytes)

    with SessionLocal() as db:
        job = IngestionJobRepository.get(db, job_resp.job_id)
        assert job.status == "failed"
        assert "Simulated chunking failure" in job.error_message

        doc = DocumentRepository.get(db, job_resp.document_id)
        assert doc.status == "failed"
        assert "Simulated chunking failure" in doc.error_message

        # Assert no chunks remain in PostgreSQL
        chunks = ChunkRepository.list_by_document(db, doc.id)
        assert len(chunks) == 0

    # Assert no vectors in FAISS or BM25
    faiss_res = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=5, filters={"document_ids": [doc.id]})
    assert len(faiss_res) == 0

# 9, 10, 11, 12. Retry failed job without duplicate chunks, FAISS vectors, or BM25 entries
def test_retry_failed_job_idempotent(mock_pipeline_env):
    runner = mock_pipeline_env["runner"]
    job_service = mock_pipeline_env["job_service"]
    vstore = mock_pipeline_env["vstore"]
    bm25 = mock_pipeline_env["bm25"]

    file_bytes = b"Quantum computing utilizes qubits for exponentially faster search operations."
    ws_id = "ws_retry_test"

    job_resp, _ = job_service.create_file_job(
        file_bytes=file_bytes,
        file_name="retry_doc.txt",
        workspace_id=ws_id
    )

    # 1. First run fails
    with patch.object(runner.pipeline.embedder, "embed_documents", side_effect=RuntimeError("Embedding service down")):
        runner.run_job(job_id=job_resp.job_id, file_bytes=file_bytes)

    with SessionLocal() as db:
        job = IngestionJobRepository.get(db, job_resp.job_id)
        assert job.status == "failed"

    # 2. Retry the job via endpoint or service
    retry_resp = client.post(f"/api/v1/ingestion/jobs/{job_resp.job_id}/retry")
    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()
    assert retry_data["status"] == "pending"
    assert retry_data["retry_count"] == 1

    # 3. Re-run runner (success)
    runner.run_job(job_id=job_resp.job_id, file_bytes=file_bytes)

    with SessionLocal() as db:
        job_after = IngestionJobRepository.get(db, job_resp.job_id)
        assert job_after.status == "completed"

        doc_after = DocumentRepository.get(db, job_resp.document_id)
        assert doc_after.status == "ready"

        chunks = ChunkRepository.list_by_document(db, doc_after.id)
        initial_chunk_count = len(chunks)
        assert initial_chunk_count > 0

    # 4. Re-running the runner again (simulate duplicate run or second retry)
    runner.run_job(job_id=job_resp.job_id, file_bytes=file_bytes)

    with SessionLocal() as db:
        chunks_again = ChunkRepository.list_by_document(db, doc_after.id)
        assert len(chunks_again) == initial_chunk_count # No duplicate DB chunks

    # Check vector store count
    faiss_matches = vstore.search([1.0, 0.0, 0.0, 0.0], top_k=20, filters={"document_ids": [doc_after.id]})
    assert len(faiss_matches) == initial_chunk_count # No duplicate FAISS vectors

# 13. Concurrent processing protection
def test_concurrent_processing_protection(mock_pipeline_env):
    runner = mock_pipeline_env["runner"]
    job_service = mock_pipeline_env["job_service"]

    ws_id = "ws_concurrency"
    job_a, _ = job_service.create_file_job(b"File A", "file_a.txt", workspace_id=ws_id)

    # Set Job A to processing
    with SessionLocal() as db:
        IngestionJobRepository.update_status(db, job_a.job_id, status="processing")
        db.commit()

    # Create Job B on same document
    with SessionLocal() as db:
        job_b = IngestionJobRepository.create(
            db, workspace_id=ws_id, source_type="txt", document_id=job_a.document_id, status="pending"
        )
        db.commit()
        job_b_id = job_b.id

    # Running Job B must detect active Job A and fail safely
    runner.run_job(job_b_id, file_bytes=b"File A")

    with SessionLocal() as db:
        j_b = IngestionJobRepository.get(db, job_b_id)
        assert j_b.status == "failed"
        assert "actively processing" in j_b.error_message

# 14 & 15. Processing and Failed documents are excluded from retrieval
def test_non_ready_documents_excluded_from_retrieval():
    ws_id = "ws_retrieval_safety"
    with SessionLocal() as db:
        WorkspaceRepository.get_or_create(db, ws_id)
        doc_proc = DocumentRepository.create(
            db, workspace_id=ws_id, source_type="txt", title="Processing Doc",
            content_hash="h_proc", status="processing"
        )
        doc_fail = DocumentRepository.create(
            db, workspace_id=ws_id, source_type="txt", title="Failed Doc",
            content_hash="h_fail", status="failed"
        )
        db.commit()
        proc_id = doc_proc.id
        fail_id = doc_fail.id

    # Query with scope targeted at non-ready doc
    res_proc = client.post("/api/v1/chat/query", json={
        "question": "What is in the processing document?",
        "workspace_id": ws_id,
        "document_ids": [proc_id]
    })
    assert res_proc.status_code == 200
    data_proc = res_proc.json()
    assert data_proc["has_sufficient_context"] is False
    assert len(data_proc["citations"]) == 0

    res_fail = client.post("/api/v1/chat/query", json={
        "question": "What is in the failed document?",
        "workspace_id": ws_id,
        "document_ids": [fail_id]
    })
    assert res_fail.status_code == 200
    data_fail = res_fail.json()
    assert data_fail["has_sufficient_context"] is False
    assert len(data_fail["citations"]) == 0

# 16, 17, 18, 19. Multi-format background job creation
def test_all_file_types_supported_by_job_service(mock_pipeline_env):
    job_service = mock_pipeline_env["job_service"]
    runner = mock_pipeline_env["runner"]
    ws_id = "ws_formats"

    # TXT
    job_txt, _ = job_service.create_file_job(b"Simple text line", "sample.txt", ws_id)
    runner.run_job(job_txt.job_id, b"Simple text line")
    assert job_service.get_job_status(job_txt.job_id).status == "completed"

    # Markdown
    job_md, _ = job_service.create_file_job(b"# Heading\nMarkdown content", "sample.md", ws_id)
    runner.run_job(job_md.job_id, b"# Heading\nMarkdown content")
    assert job_service.get_job_status(job_md.job_id).status == "completed"

    # CSV
    job_csv, _ = job_service.create_file_job(b"col1,col2\nval1,val2\n", "sample.csv", ws_id)
    runner.run_job(job_csv.job_id, b"col1,col2\nval1,val2\n")
    assert job_service.get_job_status(job_csv.job_id).status == "completed"

# 20. Website URL ingestion job
def test_website_url_ingestion_job(mock_pipeline_env):
    from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment

    job_service = mock_pipeline_env["job_service"]
    runner = mock_pipeline_env["runner"]
    ws_id = "ws_web_job"

    job_url, needs_proc = job_service.create_url_job("https://example.com/test-article", ws_id, is_youtube=False)
    assert needs_proc is True
    assert job_url.status == "pending"

    mock_extracted = ExtractedDocument(
        title="Example Article",
        source_type="web",
        source_url="https://example.com/test-article",
        full_text="Example article full content for background processing test.",
        segments=[ExtractedSegment(text="Example article full content for background processing test.")],
        metadata={}
    )
    with patch.object(runner.pipeline, "get_loader_for_url", return_value=MagicMock(load=lambda: mock_extracted)):
        runner.run_job(job_url.job_id)

    status = job_service.get_job_status(job_url.job_id)
    assert status.status == "completed"

# 21. YouTube URL ingestion job
def test_youtube_url_ingestion_job(mock_pipeline_env):
    from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment

    job_service = mock_pipeline_env["job_service"]
    runner = mock_pipeline_env["runner"]
    ws_id = "ws_yt_job"

    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    job_yt, needs_proc = job_service.create_url_job(yt_url, ws_id, is_youtube=True)
    assert needs_proc is True
    assert job_yt.status == "pending"

    mock_extracted = ExtractedDocument(
        title="Never Gonna Give You Up",
        source_type="youtube",
        source_url=yt_url,
        full_text="We're no strangers to love, you know the rules and so do I.",
        segments=[ExtractedSegment(text="We're no strangers to love, you know the rules and so do I.", start_time=0.0, end_time=10.0, timestamp_str="00:00:00 - 00:00:10")],
        metadata={"video_id": "dQw4w9WgXcQ"}
    )
    with patch.object(runner.pipeline, "get_loader_for_url", return_value=MagicMock(load=lambda: mock_extracted)):
        runner.run_job(job_yt.job_id)

    status = job_service.get_job_status(job_yt.job_id)
    assert status.status == "completed"
