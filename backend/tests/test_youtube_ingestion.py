import pytest
from unittest.mock import patch, MagicMock
from typing import List
import uuid

from backend.app.services.ingestion.youtube.service import YouTubeIngestionService
from backend.app.services.ingestion.youtube.exceptions import (
    InvalidYouTubeURLError,
    TranscriptUnavailableError,
    ASRDisabledError
)
from backend.app.services.ingestion.youtube.models import TranscriptResult, TranscriptSegment
from backend.app.services.ingestion.youtube.providers.transcript_api_provider import YouTubeTranscriptApiProvider
from backend.app.services.ingestion.youtube.providers.ytdlp_provider import YtDlpTranscriptProvider
from backend.app.services.ingestion.youtube.providers.asr_provider import WhisperASRProvider
from backend.app.services.ingestion.youtube.utils import format_timestamp, parse_json3_captions, parse_vtt_captions
from backend.app.services.ingestion.chunker import MetadataAwareChunker
from backend.app.schemas.document import SourceType, DocumentChunk, ChunkMetadata
from backend.app.services.rag.engine import RAGEngine
from backend.app.schemas.rag import RAGQueryRequest

# 1. URL Parsing & Video ID Extraction
def test_valid_youtube_urls():
    service = YouTubeIngestionService()
    test_urls = [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=120s", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=trackingcode", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ]
    for url, expected_id in test_urls:
        assert service.extract_video_id(url) == expected_id, f"Failed for {url}"

def test_invalid_youtube_urls():
    service = YouTubeIngestionService()
    invalid_urls = [
        "https://example.com/video",
        "https://www.youtube.com/",
        "https://youtu.be/",
        "https://www.youtube.com/watch?v=short",
        "",
        "not_a_url",
    ]
    for url in invalid_urls:
        with pytest.raises(InvalidYouTubeURLError):
            service.extract_video_id(url)

# 2. Timestamp formatting & Caption Parsing
def test_timestamp_formatting():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(3665) == "01:01:05"

def test_parse_json3_captions():
    json3_data = {
        "events": [
            {
                "tStartMs": 1000,
                "dDurationMs": 4000,
                "segs": [{"utf8": "First caption sentence."}]
            },
            {
                "tStartMs": 6000,
                "dDurationMs": 5000,
                "segs": [{"utf8": "Second caption"}, {"utf8": " sentence."}]
            }
        ]
    }
    segments = parse_json3_captions(json3_data)
    assert len(segments) == 2
    assert segments[0].text == "First caption sentence."
    assert segments[0].start == 1.0
    assert segments[0].end == 5.0
    assert segments[0].timestamp_str == "00:01 – 00:05"
    assert segments[1].text == "Second caption sentence."
    assert segments[1].start == 6.0
    assert segments[1].end == 11.0

def test_parse_vtt_captions():
    vtt = """WEBVTT

00:00:02.000 --> 00:00:05.500
Hello from WebVTT subtitles.

00:01:10.000 --> 00:01:15.000
<c>Second</c> <b>formatted</b> line.
"""
    segments = parse_vtt_captions(vtt)
    assert len(segments) == 2
    assert segments[0].text == "Hello from WebVTT subtitles."
    assert segments[0].start == 2.0
    assert segments[0].end == 5.5
    assert segments[1].text == "Second formatted line."
    assert segments[1].start == 70.0
    assert segments[1].end == 75.0

# 3. Successful Primary Transcript Provider
def test_primary_transcript_api_provider():
    provider = YouTubeTranscriptApiProvider()
    mock_api = MagicMock()
    mock_api.fetch.return_value = [
        {"text": "Welcome to neural networks.", "start": 0.0, "duration": 5.0},
        {"text": "Backpropagation computes gradients.", "start": 5.0, "duration": 4.0}
    ]
    with patch.object(provider, "_get_api_client", return_value=mock_api):
        res = provider.fetch_transcript("dQw4w9WgXcQ", "https://youtube.com/watch?v=dQw4w9WgXcQ")
        assert res is not None
        assert res.provider == "youtube_transcript_api"
        assert len(res.segments) == 2
        assert res.segments[0].timestamp_str == "00:00 – 00:05"
        assert res.segments[1].text == "Backpropagation computes gradients."
        assert "Welcome to neural networks." in res.full_text

# 4. Fallback Provider Activation (Primary fails -> yt-dlp subtitles succeeds)
def test_fallback_provider_activation():
    mock_primary = MagicMock()
    mock_primary.name = "youtube_transcript_api"
    mock_primary.fetch_transcript.return_value = None

    mock_secondary = MagicMock()
    mock_secondary.name = "ytdlp_subtitles"
    mock_secondary.fetch_transcript.return_value = TranscriptResult(
        video_id="dQw4w9WgXcQ",
        title="Fallback Video Title",
        channel="Test Channel",
        language="en",
        segments=[
            TranscriptSegment(text="Recovered from yt-dlp.", start=0.0, end=4.0, timestamp_str="00:00 – 00:04")
        ],
        provider="ytdlp_subtitles",
        full_text="Recovered from yt-dlp.",
        duration_seconds=4.0
    )

    service = YouTubeIngestionService(providers=[mock_primary, mock_secondary])
    doc = service.ingest_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert mock_primary.fetch_transcript.called
    assert mock_secondary.fetch_transcript.called
    assert doc.title == "Fallback Video Title"
    assert doc.metadata["provider"] == "ytdlp_subtitles"
    assert len(doc.segments) == 1
    assert doc.segments[0].timestamp_str == "00:00 – 00:04"

# 5. ASR Disabled Behavior
def test_all_captions_fail_asr_disabled():
    mock_primary = MagicMock()
    mock_primary.name = "youtube_transcript_api"
    mock_primary.fetch_transcript.return_value = None

    mock_secondary = MagicMock()
    mock_secondary.name = "ytdlp_subtitles"
    mock_secondary.fetch_transcript.return_value = None

    asr_provider = WhisperASRProvider()
    service = YouTubeIngestionService(providers=[mock_primary, mock_secondary, asr_provider])

    with patch("backend.app.core.config.settings.YOUTUBE_ASR_ENABLED", False):
        with pytest.raises(TranscriptUnavailableError) as exc_info:
            service.ingest_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "Transcripts may be disabled" in str(exc_info.value)
        assert "ASR fallback" in str(exc_info.value)

# 6. Timestamp Preservation in Chunker
def test_youtube_chunker_timestamp_preservation():
    from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment

    segments = [
        ExtractedSegment(text="Sentence 1 about transformers.", start_time=10.0, end_time=25.0, timestamp_str="00:10 – 00:25"),
        ExtractedSegment(text="Sentence 2 about attention mechanisms.", start_time=25.0, end_time=45.0, timestamp_str="00:25 – 00:45"),
        ExtractedSegment(text="Sentence 3 about multi-head attention.", start_time=45.0, end_time=70.0, timestamp_str="00:45 – 01:10")
    ]
    doc = ExtractedDocument(
        title="Attention Is All You Need Lecture",
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        full_text="Sentence 1 about transformers. Sentence 2 about attention mechanisms. Sentence 3 about multi-head attention.",
        metadata={"video_id": "dQw4w9WgXcQ"},
        segments=segments
    )

    chunker = MetadataAwareChunker(chunk_size=1000, chunk_overlap=100)
    chunks = chunker.chunk_document(doc, document_id="yt-doc-123", workspace_id="default")

    assert len(chunks) >= 1
    first_chunk = chunks[0]
    assert first_chunk.metadata.source_type == SourceType.YOUTUBE
    assert first_chunk.metadata.start_time == 10.0
    assert first_chunk.metadata.end_time == 70.0
    assert first_chunk.metadata.timestamp_str == "00:10 – 01:10"

# 7. YouTube Citation Generation in RAG Engine
def test_youtube_citation_generation():
    chunk_meta = ChunkMetadata(
        chunk_id="chunk-yt-99",
        document_id="doc-yt-1",
        workspace_id="default",
        source_type=SourceType.YOUTUBE,
        source_name="Deep Learning Lecture 01",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        start_time=120.0,
        end_time=185.0,
        timestamp_str="02:00 – 03:05",
        chunk_index=0
    )
    chunk = DocumentChunk(
        chunk_id="chunk-yt-99",
        content="Backpropagation uses the chain rule to calculate gradients.",
        metadata=chunk_meta
    )

    class MockRetriever:
        def retrieve(self, query, top_k=5, filters=None):
            return [(chunk, 0.95)]

    class MockLLM:
        def generate(self, prompt, system_prompt=None):
            return "According to [Source 1], backpropagation uses the chain rule."

    engine = RAGEngine(retriever=MockRetriever(), llm=MockLLM())
    req = RAGQueryRequest(question="How does backpropagation work?", top_k=1)
    res = engine.query(req)

    assert res.has_sufficient_context
    assert len(res.citations) == 1
    cit = res.citations[0]
    assert cit.source_type == SourceType.YOUTUBE
    assert cit.start_time == 120.0
    assert cit.end_time == 185.0
    assert cit.timestamp_str == "02:00 – 03:05"
    assert cit.chunk_id == "chunk-yt-99"

# 8. PostgreSQL Persistence, FAISS/BM25 Consistency, and Deletion
def test_youtube_pipeline_persistence_and_cleanup():
    from backend.app.db.session import SessionLocal
    from backend.app.repositories.document_repo import DocumentRepository
    from backend.app.repositories.chunk_repo import ChunkRepository
    from backend.app.services.ingestion.pipeline import IngestionPipeline
    from backend.app.services.vector_store.faiss_store import FAISSVectorStore
    from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
    from backend.app.services.rag.bm25 import BM25Retriever
    from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment

    embedder = HuggingFaceEmbedder()
    vstore = FAISSVectorStore(dimension=embedder.dimension)
    bm25 = BM25Retriever()
    pipeline = IngestionPipeline(
        embedder=embedder,
        vector_store=vstore,
        keyword_retriever=bm25,
        session_factory=SessionLocal
    )

    mock_doc = ExtractedDocument(
        title="Micrograd From Scratch",
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=VMj-3S1tku0",
        full_text="Building micrograd engine with backpropagation and neural nets.",
        metadata={"video_id": "VMj-3S1tku0", "channel": "Andrej Karpathy"},
        segments=[
            ExtractedSegment(
                text="Building micrograd engine with backpropagation and neural nets.",
                start_time=0.0,
                end_time=60.0,
                timestamp_str="00:00 – 01:00",
                section_title="Segment 00:00 – 01:00"
            )
        ]
    )

    ws_id = f"ws-yt-{uuid.uuid4().hex[:8]}"

    with patch("backend.app.services.ingestion.loaders.youtube_loader.YouTubeLoader.load", return_value=mock_doc):
        resp = pipeline.process_url("https://www.youtube.com/watch?v=VMj-3S1tku0", workspace_id=ws_id)
        assert resp.id is not None
        assert resp.source_type == "youtube"
        assert resp.chunk_count >= 1

        # 9. Verify PostgreSQL chunk persistence
        with SessionLocal() as db:
            doc_in_db = DocumentRepository.get(db, resp.id)
            assert doc_in_db is not None
            assert doc_in_db.source_type == "youtube"

            chunks_in_db = ChunkRepository.list_by_document(db, resp.id)
            assert len(chunks_in_db) == resp.chunk_count
            chunk_rec = chunks_in_db[0]
            assert chunk_rec.source_type == "youtube"
            assert chunk_rec.start_time == 0.0
            assert chunk_rec.end_time == 60.0
            assert chunk_rec.timestamp_str == "00:00 – 01:00"

            # 10. Verify FAISS / BM25 consistency
            initial_faiss_count = vstore.index.ntotal
            initial_bm25_count = len(bm25.chunks)
            assert initial_faiss_count >= 1
            assert initial_bm25_count >= 1

        # 11. Test deletion cleanup
        del_success = pipeline.delete_document(resp.id)
        assert del_success

        with SessionLocal() as db:
            assert DocumentRepository.get(db, resp.id) is None
            assert len(ChunkRepository.list_by_document(db, resp.id)) == 0

        assert vstore.index.ntotal == initial_faiss_count - resp.chunk_count
        assert len(bm25.chunks) == initial_bm25_count - resp.chunk_count

# 12. API Endpoint Testing
def test_api_youtube_endpoint_validation():
    from starlette.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    # Invalid URL returns 400
    res_bad = client.post("/api/v1/documents/youtube", json={"url": "https://invalid.com/bad"})
    assert res_bad.status_code == 400
    assert "Invalid YouTube URL" in res_bad.json()["detail"] or "valid" in res_bad.json()["detail"].lower()

