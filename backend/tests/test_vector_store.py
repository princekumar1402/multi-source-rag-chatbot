import os
import shutil
import pytest
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType

def test_faiss_vector_store(tmp_path):
    store_dir = str(tmp_path / "vector_store")
    dim = 4
    store = FAISSVectorStore(dimension=dim, store_dir=store_dir)

    c1 = DocumentChunk(
        chunk_id="c1",
        content="Artificial intelligence and machine learning",
        metadata=ChunkMetadata(
            chunk_id="c1",
            document_id="doc-1",
            workspace_id="ws-1",
            source_type=SourceType.WEB,
            source_name="AI Intro",
            source_url="https://example.com/ai"
        )
    )
    c2 = DocumentChunk(
        chunk_id="c2",
        content="Operating systems and memory paging",
        metadata=ChunkMetadata(
            chunk_id="c2",
            document_id="doc-2",
            workspace_id="ws-1",
            source_type=SourceType.PDF,
            source_name="OS Book",
            page_number=12
        )
    )

    vec1 = [1.0, 0.0, 0.0, 0.0]
    vec2 = [0.0, 1.0, 0.0, 0.0]

    # Test adding chunks
    ids = store.add_chunks([c1, c2], [vec1, vec2])
    assert len(ids) == 2
    assert store.count() == 2

    # Test search with query close to vec1
    query_vec = [0.9, 0.1, 0.0, 0.0]
    results = store.search(query_vec, top_k=2)
    assert len(results) == 2
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "c1"
    assert score > 0.8

    # Test metadata filter (filter by document_id)
    filtered = store.search(query_vec, top_k=2, filters={"document_ids": ["doc-2"]})
    assert len(filtered) == 1
    assert filtered[0][0].chunk_id == "c2"

    # Test deletion
    deleted = store.delete_document("doc-1")
    assert deleted is True
    assert store.count() == 1
    assert store.search(query_vec, top_k=2)[0][0].chunk_id == "c2"
