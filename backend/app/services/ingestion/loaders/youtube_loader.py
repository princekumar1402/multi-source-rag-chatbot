from typing import List, Optional

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.services.ingestion.youtube.service import YouTubeIngestionService
from backend.app.services.ingestion.youtube.utils import format_timestamp
from backend.app.services.ingestion.youtube.exceptions import YouTubeIngestionError
from backend.app.core.logging import logger

__all__ = ["format_timestamp", "YouTubeLoader"]

class YouTubeLoader(BaseLoader):
    """
    Ingests YouTube video transcripts and extracts segment timestamps
    using a robust multi-provider fallback architecture.
    """

    def __init__(self, url: str, languages: Optional[List[str]] = None):
        self.url = url
        self.languages = languages or ["en"]
        self.service = YouTubeIngestionService(languages=self.languages)
        try:
            self.video_id = self.service.extract_video_id(url)
        except Exception as e:
            raise ValueError(f"Could not extract a valid YouTube video ID from URL: {url}") from e

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Backward-compatible helper method."""
        try:
            return self.service.extract_video_id(url)
        except Exception:
            return None

    def _fetch_video_title(self) -> str:
        """Backward-compatible helper method."""
        return self.service.fetch_video_title(self.url, self.video_id)

    def load(self) -> ExtractedDocument:
        logger.info(f"Loading transcript for YouTube video: {self.video_id}")
        return self.service.ingest_transcript(self.url)
