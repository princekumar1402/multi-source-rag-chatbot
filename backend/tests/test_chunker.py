import pytest
from backend.app.services.ingestion.chunker import MetadataAwareChunker
from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment

def test_chunker_metadata_preservation():
    chunker = MetadataAwareChunker(chunk_size=100, chunk_overlap=20)
    
    segments = [
        ExtractedSegment(text="First paragraph of section one.", start_time=0.0, end_time=15.0, section_title="Intro"),
        ExtractedSegment(text="Second paragraph of section one with more words.", start_time=15.0, end_time=35.0, section_title="Intro"),
        ExtractedSegment(text="Now we enter section two which talks about architecture.", start_time=35.0, end_time=55.0, section_title="Architecture"),
    ]

    doc = ExtractedDocument(
        title="Test Document",
        source_type="youtube",
        source_url="https://youtube.com/watch?v=123",
        full_text="First paragraph of section one. Second paragraph. Now we enter section two.",
        segments=segments
    )

    chunks = chunker.chunk_document(doc=doc, document_id="doc-test-1", workspace_id="ws-test")
    assert len(chunks) >= 1
    
    # Check that metadata was preserved
    first_chunk = chunks[0]
    assert first_chunk.metadata.document_id == "doc-test-1"
    assert first_chunk.metadata.workspace_id == "ws-test"
    assert first_chunk.metadata.source_name == "Test Document"
    assert first_chunk.metadata.timestamp_str is not None
    assert "00:00" in first_chunk.metadata.timestamp_str
