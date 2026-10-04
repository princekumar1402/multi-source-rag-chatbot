# Phase 5: Production-Grade YouTube Ingestion & Transcript Fallback

## 1. Executive Summary

Phase 5 introduces a robust, multi-tier fallback architecture for YouTube video ingestion into the enterprise Multi-Source RAG Platform. It resolves legacy transcript extraction issues caused by YouTube API shifts, missing manual captions, and IP rate limits, while preserving timestamp accuracy, PostgreSQL persistence, FAISS dense indexing, BM25 lexical search, and precise LLM citations.

---

## 2. YouTube Ingestion Architecture

```
                       YouTube URL Input
                              │
                              ▼
            URL Validation & Video ID Extraction
         (Regex + hostname check: watch, youtu.be,
            shorts, embed, live, mobile)
                              │
                              ▼
                  YouTubeIngestionService
                              │
            ┌─────────────────┴─────────────────┐
            │       Transcript Provider Chain    │
            │                                   │
            │  Tier 1: YouTubeTranscriptApi     │
            │          (Fast, multi-lang)       │
            │                 │ (on failure)    │
            │                 ▼                 │
            │  Tier 2: YtDlpTranscriptProvider  │
            │          (JSON3/VTT captions      │
            │           without downloading)    │
            │                 │ (on failure)    │
            │                 ▼                 │
            │  Tier 3: WhisperASRProvider       │
            │          (Audio-only local ASR    │
            │           when enabled)           │
            └─────────────────┬─────────────────┘
                              │
                              ▼
                  Normalized Segments
            (text, start_sec, end_sec, "MM:SS – MM:SS")
                              │
                              ▼
                  MetadataAwareChunker
            (Window accumulation + boundary preservation)
                              │
                              ▼
                  PostgreSQL Persistence
            (Document, Chunks with timestamps, IngestionJob)
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
        FAISS Vector Store             BM25 Retriever
      (Dense embeddings)           (Lexical inverted index)
               │                             │
               └──────────────┬──────────────┘
                              ▼
                     RAG Hybrid Engine
            (RRF fusion + reranker + citations)
```

---

## 3. Provider Chain & Fallback Mechanism

### Tier 1: `YouTubeTranscriptApiProvider`
* **Implementation**: Wraps `youtube-transcript-api` with automatic detection of modern instance APIs (`api.fetch()`, `api.list()`) and legacy class-based methods.
* **Languages**: Ingests preferred languages (default `['en']`) with auto-discovery fallback across all available creator transcripts.
* **Latency**: Extremely fast (~100–300ms) with zero media streaming.

### Tier 2: `YtDlpTranscriptProvider`
* **Implementation**: Utilizes `yt-dlp` info extraction (`skip_download=True`) to discover official YouTube caption tracks.
* **Caption Format Parsing**:
  - **Native JSON3 (`parse_json3_captions`)**: Parses YouTube's native JSON3 event streams, extracting millisecond-accurate start/duration timestamps and aggregating text segments.
  - **WebVTT (`parse_vtt_captions`)**: Parses standard WebVTT cue timings (`HH:MM:SS.mmm --> HH:MM:SS.mmm`) with regex stripping of HTML/VTT styling tags.
* **Advantage**: Bypasses browser-scraping blocks by using YouTube's mobile/web player endpoints without downloading video or audio streams.

### Tier 3: `WhisperASRProvider`
* **Implementation**: Local audio-only transcription using `faster-whisper`.
* **Resource Safety & Safeguards**:
  - Probes video duration before download; rejects videos exceeding `YOUTUBE_MAX_DURATION_SECONDS` (default: 1800s / 30m).
  - Enforces `YOUTUBE_MAX_AUDIO_SIZE_MB` (default: 50MB).
  - Only extracts audio (`ba/b` format), avoiding video stream overhead.
  - Automatically isolates work inside a temporary directory and guarantees complete file deletion in a `finally` block.
  - Generates word/segment-level timestamps preserved through the chunking pipeline.

---

## 4. Configuration Reference

The following settings are configured in `backend/app/core/config.py` and configurable via `.env`:

| Variable | Default | Description |
|---|---|---|
| `YOUTUBE_TRANSCRIPT_PROVIDER` | `auto` | Provider strategy: `auto`, `youtube_transcript_api`, `ytdlp`, or `whisper`. |
| `YOUTUBE_LANGUAGES` | `["en"]` | Target transcript languages in descending priority. |
| `YOUTUBE_ASR_ENABLED` | `false` | Enable Whisper local ASR fallback when captions are unavailable. |
| `YOUTUBE_ASR_MODEL` | `tiny` | Faster-Whisper model size (`tiny`, `base`, `small`, `medium`). |
| `YOUTUBE_MAX_DURATION_SECONDS` | `1800` | Maximum video duration (30 min) permitted for ASR fallback. |
| `YOUTUBE_MAX_AUDIO_SIZE_MB` | `50` | Maximum audio download size permitted for ASR processing. |

---

## 5. Timestamp Preservation & Grounded Citations

Every YouTube chunk contains strict timestamp bounds:
* `start_time`: Float seconds from start of video (e.g. `0.0`).
* `end_time`: Float seconds to end of chunk (e.g. `73.32`).
* `timestamp_str`: Human-readable range (e.g. `00:00 – 01:13`).

### Verified Citation Flow
When a user asks questions about a YouTube video:
1. Retrieval fetches chunks from FAISS and BM25 matching the user query.
2. `RAGEngine` constructs context blocks with `[Source X] Title (MM:SS – MM:SS)`.
3. The LLM synthesizes answers with citations: `[Source 1]`.
4. Output `Citation` objects contain exact video timestamps and links:
```json
{
  "source_type": "youtube",
  "source_title": "Proof Of Trump's Receding Power?: Iran Celebrates US Troop Exit From Iraq | Firstpost Live",
  "timestamp_str": "00:00 – 01:13",
  "start_time": 0.0,
  "end_time": 73.32,
  "chunk_id": "99ce4076-2e55-46aa-b2b9-e1de4e51bfbe"
}
```

---

## 6. PostgreSQL Persistence & Index Synchronization

* **Document Entity**: Stored in `documents` table with `source_type = 'youtube'`, `source_url = 'https://www.youtube.com/watch?v=...'`, and `doc_metadata` containing `video_id`, `channel`, `provider`, `duration_seconds`.
* **Chunk Entity**: Stored in `chunks` table with UUID `id`, `start_time`, `end_time`, `timestamp_str`, `chunk_index`.
* **Vector Store / BM25 Consistency**: The PostgreSQL chunk `id` is identical to the FAISS metadata ID and BM25 document key.
* **Cascade Deletion**: Purging a YouTube document purges all vectors from FAISS, all tokens from BM25, and all rows from PostgreSQL.

---

## 7. Error Handling & Security

1. **URL Validation**: Rejects arbitrary or malicious URLs; strictly validates 11-character alphanumeric YouTube IDs.
2. **Resource Bounds**: Probes video duration before any audio extraction to prevent disk exhaustion.
3. **Structured Exceptions**:
   - `InvalidYouTubeURLError` (HTTP 400)
   - `VideoUnavailableError` (HTTP 400)
   - `TranscriptUnavailableError` (HTTP 400)
   - `VideoDurationExceededError` (HTTP 400)
   - `ASRDisabledError` (HTTP 400)
   - `ASRDependencyMissingError` (HTTP 400)
   - `AudioExtractionError` (HTTP 400)
4. **User Privacy**: No internal stack traces, API keys, or raw system paths exposed in API error payloads.

---

## 8. Verification & Test Suite

### Full Automated Regression Suite
* **Previous Tests (Phases 1–4)**: 47 passed
* **New YouTube Tests**: 12 passed
* **Total Passing**: **59 passed in 35.5s**
* **Frontend Build**: `tsc && vite build` succeeded in 2.05s

### Live Video Validation Results
1. **Video 1 (Real user URL)**: `https://www.youtube.com/watch?v=0RvRgjhOf-Y`
   - *Title*: Proof Of Trump's Receding Power?: Iran Celebrates US Troop Exit From Iraq | Firstpost Live
   - *Provider*: `youtube_transcript_api`
   - *Segments*: 198 extracted
   - *Chunks*: 7 indexed and persisted in PostgreSQL, FAISS, and BM25
   - *RAG Query*: Verified with grounded answers and 5 accurate timestamp citations (`00:00 – 01:13`, `05:33 – 06:55`, `02:12 – 03:24`, etc.).
2. **Video 2 (Public music/captions)**: `https://www.youtube.com/watch?v=dQw4w9WgXcQ`
   - *Title*: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
   - *Provider*: `youtube_transcript_api` / `ytdlp_subtitles`
   - *Chunks*: 3 indexed and persisted
   - *Status*: Ready, grounded queries verified.

---

## 9. Known Limitations

1. **DRM / Age-Restricted / Paid Videos**: Videos requiring user authentication or paid memberships cannot be retrieved without cookies.
2. **Creator-Disabled Subtitles with ASR Disabled**: If a video creator disables both manual and automated captions, and `YOUTUBE_ASR_ENABLED=false`, ingestion will cleanly return HTTP 400 explaining that transcripts are disabled and ASR fallback is inactive.
3. **ASR Execution Time**: When ASR is enabled for long videos (e.g. 15–30 minutes) on CPU, transcription may take 30–90 seconds depending on CPU speed and model size (`tiny` vs `base`).
