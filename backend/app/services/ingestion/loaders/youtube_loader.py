import re
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.logging import logger

def format_timestamp(seconds: float) -> str:
    """Converts seconds into HH:MM:SS or MM:SS format."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

class YouTubeLoader(BaseLoader):
    """
    Ingests YouTube video transcripts and extracts segment timestamps.
    """

    def __init__(self, url: str, languages: Optional[List[str]] = None):
        self.url = url
        self.languages = languages or ["en"]
        self.video_id = self._extract_video_id(url)
        if not self.video_id:
            raise ValueError(f"Could not extract a valid YouTube video ID from URL: {url}")

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Supports watch?v=, youtu.be, shorts, and embed formats."""
        parsed = urlparse(url)
        if parsed.hostname in ("www.youtube.com", "youtube.com"):
            if parsed.path == "/watch":
                qs = parse_qs(parsed.query)
                return qs.get("v", [None])[0]
            elif parsed.path.startswith("/embed/"):
                return parsed.path.split("/")[2]
            elif parsed.path.startswith("/shorts/"):
                return parsed.path.split("/")[2]
        elif parsed.hostname == "youtu.be":
            return parsed.path.lstrip("/")
        return None

    def _fetch_video_title(self) -> str:
        """Fetches video title using official public YouTube oEmbed endpoint."""
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={self.url}&format=json"
            resp = requests.get(oembed_url, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("title", f"YouTube Video ({self.video_id})")
        except Exception as e:
            logger.warning(f"Could not fetch YouTube title via oEmbed: {e}")
        return f"YouTube Video ({self.video_id})"

    def load(self) -> ExtractedDocument:
        logger.info(f"Loading transcript for YouTube video: {self.video_id}")
        title = self._fetch_video_title()

        try:
            # First try configured languages
            transcript_list = YouTubeTranscriptApi.get_transcript(self.video_id, languages=self.languages)
        except Exception as primary_err:
            logger.warning(f"Failed to fetch transcript with primary languages {self.languages}: {primary_err}. Attempting auto-discovery.")
            try:
                # Fallback: get any available transcript
                transcript_transcripts = YouTubeTranscriptApi.list_transcripts(self.video_id)
                available = transcript_transcripts.find_transcript(self.languages)
                transcript_list = available.fetch()
            except Exception as e:
                raise RuntimeError(
                    f"Unable to retrieve YouTube transcript for video {self.video_id}. "
                    "Transcripts may be disabled or restricted by the video creator."
                ) from e

        segments: List[ExtractedSegment] = []
        full_text_parts: List[str] = []

        for item in transcript_list:
            text = item.get("text", "").strip()
            if not text:
                continue
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            end = start + duration
            time_str = f"{format_timestamp(start)} – {format_timestamp(end)}"

            full_text_parts.append(text)
            segments.append(
                ExtractedSegment(
                    text=text,
                    start_time=start,
                    end_time=end,
                    timestamp_str=time_str,
                    section_title=f"Segment {time_str}"
                )
            )

        full_text = " ".join(full_text_parts)

        return ExtractedDocument(
            title=title,
            source_type="youtube",
            source_url=f"https://www.youtube.com/watch?v={self.video_id}",
            full_text=full_text,
            metadata={
                "video_id": self.video_id,
                "segment_count": len(segments),
                "url": f"https://www.youtube.com/watch?v={self.video_id}"
            },
            segments=segments
        )
