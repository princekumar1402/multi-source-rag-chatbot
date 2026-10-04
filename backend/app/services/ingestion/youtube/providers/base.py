from abc import ABC, abstractmethod
from typing import List, Optional
from backend.app.services.ingestion.youtube.models import TranscriptResult

class BaseYouTubeTranscriptProvider(ABC):
    """
    Abstract Base Class for YouTube transcript extraction providers.
    All providers must return a normalized TranscriptResult or None / raise a typed exception.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        pass

    @abstractmethod
    def fetch_transcript(
        self,
        video_id: str,
        url: str,
        languages: Optional[List[str]] = None,
        title_hint: Optional[str] = None
    ) -> Optional[TranscriptResult]:
        """
        Attempts to retrieve and normalize transcripts.
        Returns TranscriptResult if successful, or None/raises exception if unavailable.
        """
        pass
