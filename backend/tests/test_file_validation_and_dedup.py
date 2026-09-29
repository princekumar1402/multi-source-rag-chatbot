import pytest
from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.schemas.document import DocumentStatus, SourceType
from backend.app.core.config import settings
import pymupdf

def test_file_validation(tmp_path):
    embedder = HuggingFaceEmbedder()
    store = FAISSVectorStore(dimension=embedder.dimension, store_dir=str(tmp_path / "vs"))
    pipeline = IngestionPipeline(embedder=embedder, vector_store=store)

    # 1. Unsupported extension
    with pytest.raises(ValueError, match="Unsupported file format"):
        pipeline.process_file(b"fake binary content", "malware.exe")

    # 2. Empty file
    with pytest.raises(ValueError, match="is empty"):
        pipeline.process_file(b"", "empty.txt")

    # 3. Invalid PDF magic bytes
    with pytest.raises(ValueError, match="does not appear to be a valid PDF"):
        pipeline.process_file(b"This is just plain text, not a PDF!", "fake.pdf")

    # 4. Oversized file validation
    original_max = settings.MAX_FILE_SIZE_MB
    try:
        settings.MAX_FILE_SIZE_MB = 1 # 1 MB limit for test
        large_bytes = b"0" * (2 * 1024 * 1024) # 2 MB
        with pytest.raises(ValueError, match="exceeds maximum allowed"):
            pipeline.process_file(large_bytes, "large.txt")
    finally:
        settings.MAX_FILE_SIZE_MB = original_max

def test_duplicate_file_deduplication(tmp_path):
    embedder = HuggingFaceEmbedder()
    store = FAISSVectorStore(dimension=embedder.dimension, store_dir=str(tmp_path / "vs"))
    pipeline = IngestionPipeline(embedder=embedder, vector_store=store)

    doc_text = b"Unique content for deduplication test.\n\nSecond paragraph."

    # First upload
    doc1 = pipeline.process_file(doc_text, "notes.txt", workspace_id="ws_dedup")
    assert doc1.status == DocumentStatus.READY
    initial_chunks = store.count("ws_dedup")
    assert initial_chunks > 0

    # Second upload of the identical file
    doc2 = pipeline.process_file(doc_text, "notes_copy.txt", workspace_id="ws_dedup")
    assert doc2.id == doc1.id # Returned existing document
    assert store.count("ws_dedup") == initial_chunks # No duplicate vectors added
