import re
import requests
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment
from backend.app.services.ingestion.youtube.models import TranscriptResult
from backend.app.services.ingestion.youtube.exceptions import (
    YouTubeIngestionError,
    InvalidYouTubeURLError,
    TranscriptUnavailableError,
    ASRDisabledError
)
from backend.app.services.ingestion.youtube.providers.base import BaseYouTubeTranscriptProvider
from backend.app.services.ingestion.youtube.providers.transcript_api_provider import YouTubeTranscriptApiProvider
from backend.app.services.ingestion.youtube.providers.ytdlp_provider import YtDlpTranscriptProvider
from backend.app.services.ingestion.youtube.providers.asr_provider import WhisperASRProvider
from backend.app.core.config import settings
from backend.app.core.logging import logger

YOUTUBE_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")

class YouTubeIngestionService:
    """
    Coordinates YouTube URL validation, video ID extraction, and multi-provider
    fallback transcript extraction (youtube-transcript-api -> yt-dlp -> Whisper ASR).
    """

    def __init__(
        self,
        providers: Optional[List[BaseYouTubeTranscriptProvider]] = None,
        languages: Optional[List[str]] = None
    ):
        self.languages = languages or getattr(settings, "YOUTUBE_LANGUAGES", ["en"])
        if providers:
            self.providers = providers
        else:
            self.providers = self._build_default_providers()

    def _build_default_providers(self) -> List[BaseYouTubeTranscriptProvider]:
        configured = getattr(settings, "YOUTUBE_TRANSCRIPT_PROVIDER", "auto").lower()
        if configured == "youtube_transcript_api":
            return [YouTubeTranscriptApiProvider()]
        elif configured in ("ytdlp", "ytdlp_subtitles"):
            return [YtDlpTranscriptProvider()]
        elif configured in ("whisper", "whisper_asr"):
            return [WhisperASRProvider()]
        else:
            # Auto: primary api -> yt-dlp subtitles -> whisper ASR fallback
            return [
                YouTubeTranscriptApiProvider(),
                YtDlpTranscriptProvider(),
                WhisperASRProvider()
            ]

    def extract_video_id(self, url: str) -> str:
        """
        Extracts and strictly validates the 11-character YouTube video ID.
        Supports watch?v=, youtu.be, /embed/, /shorts/, /live/, and /v/ URLs.
        """
        if not url or not isinstance(url, str):
            raise InvalidYouTubeURLError("Provided YouTube URL is empty or invalid.")

        clean_url = url.strip()
        parsed = urlparse(clean_url)
        hostname = (parsed.hostname or "").lower()

        # Handle schemes without http(s)
        if not hostname and ("youtube.com" in clean_url or "youtu.be" in clean_url):
            parsed = urlparse(f"https://{clean_url}")
            hostname = (parsed.hostname or "").lower()

        video_id: Optional[str] = None

        if hostname in ("www.youtube.com", "youtube.com", "m.youtube.com", "music.youtube.com"):
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                video_id = qs.get("v", [None])[0]
            elif parsed.path.startswith(("/embed/", "/shorts/", "/live/", "/v/")):
                parts = parsed.path.strip("/").split("/")
                if len(parts) >= 2:
                    video_id = parts[1]
        elif hostname in ("youtu.be", "www.youtu.be"):
            path_part = parsed.path.strip("/").split("?")[0].split("&")[0]
            if path_part:
                video_id = path_part

        if not video_id or not YOUTUBE_ID_REGEX.match(video_id):
            raise InvalidYouTubeURLError(
                f"Could not extract a valid 11-character YouTube video ID from URL: '{url}'"
            )

        return video_id

    def fetch_video_title(self, url: str, video_id: str) -> str:
        """Fetches video title using official public YouTube oEmbed endpoint."""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
            resp = requests.get(oembed_url, timeout=5)
            if resp.status_code == 200:
                title = resp.json().get("title")
                if title:
                    return title.strip()
        except Exception as e:
            logger.debug(f"Could not fetch YouTube title via oEmbed for {video_id}: {e}")
        return f"YouTube Video ({video_id})"

    def ingest_transcript(
        self,
        url: str,
        custom_title: Optional[str] = None
    ) -> ExtractedDocument:
        """
        Executes the full YouTube transcript ingestion pipeline across the provider chain.
        Returns normalized ExtractedDocument preserving timestamped segments.
        """
        video_id = self.extract_video_id(url)
        clean_url = f"https://www.youtube.com/watch?v={video_id}"
        resolved_title = custom_title or self.fetch_video_title(clean_url, video_id)

        last_error: Optional[Exception] = None
        result: Optional[TranscriptResult] = None

        for provider in self.providers:
            try:
                logger.info(f"Attempting transcript extraction using provider: '{provider.name}' for {video_id}")
                res = provider.fetch_transcript(
                    video_id=video_id,
                    url=clean_url,
                    languages=self.languages,
                    title_hint=resolved_title
                )
                if res and res.segments:
                    result = res
                    logger.info(f"Successfully retrieved transcript for {video_id} using '{provider.name}' ({len(res.segments)} segments)")
                    break
            except ASRDisabledError as asr_err:
                logger.info(f"Provider '{provider.name}' skipped: {asr_err}")
                last_error = asr_err
            except Exception as prov_err:
                logger.warning(f"Provider '{provider.name}' failed for video {video_id}: {prov_err}")
                last_error = prov_err

        if not result or not result.segments:
            msg = (
                f"Unable to retrieve YouTube transcript for video {video_id}. "
                "Transcripts may be disabled or restricted by the video creator, and ASR fallback is either disabled or unavailable."
            )
            if last_error and not isinstance(last_error, ASRDisabledError):
                msg += f" (Detail: {last_error})"
            raise TranscriptUnavailableError(msg)

        # Convert normalized TranscriptResult to ExtractedDocument
        segments: List[ExtractedSegment] = []
        for s in result.segments:
            segments.append(
                ExtractedSegment(
                    text=s.text,
                    start_time=s.start,
                    end_time=s.end,
                    timestamp_str=s.timestamp_str,
                    section_title=f"Segment {s.timestamp_str}" if s.timestamp_str else None
                )
            )

        doc_title = custom_title or result.title or resolved_title

        return ExtractedDocument(
            title=doc_title,
            source_type="youtube",
            source_url=clean_url,
            full_text=result.full_text,
            metadata={
                "video_id": result.video_id,
                "channel": result.channel,
                "language": result.language,
                "provider": result.provider,
                "segment_count": len(segments),
                "duration_seconds": result.duration_seconds,
                "url": clean_url
            },
            segments=segments
        )
