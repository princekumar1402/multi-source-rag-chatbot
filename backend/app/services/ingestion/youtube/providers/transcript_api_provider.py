from typing import List, Optional, Any
from youtube_transcript_api import YouTubeTranscriptApi

from backend.app.services.ingestion.youtube.providers.base import BaseYouTubeTranscriptProvider
from backend.app.services.ingestion.youtube.models import TranscriptResult, TranscriptSegment
from backend.app.services.ingestion.youtube.utils import format_timestamp
from backend.app.core.logging import logger

class YouTubeTranscriptApiProvider(BaseYouTubeTranscriptProvider):
    """
    Primary transcript provider using youtube-transcript-api.
    Supports both modern instance-based API (fetch/list) and legacy class-based API (get_transcript/list_transcripts).
    """

    @property
    def name(self) -> str:
        return "youtube_transcript_api"

    def _get_api_client(self) -> Any:
        try:
            return YouTubeTranscriptApi()
        except TypeError:
            return YouTubeTranscriptApi

    def fetch_transcript(
        self,
        video_id: str,
        url: str,
        languages: Optional[List[str]] = None,
        title_hint: Optional[str] = None
    ) -> Optional[TranscriptResult]:
        langs = languages or ["en"]
        logger.info(f"[{self.name}] Attempting transcript fetch for {video_id} with languages {langs}")

        api = self._get_api_client()
        transcript_list = None
        detected_lang = langs[0]

        # 1. Direct fetch with preferred languages
        try:
            if hasattr(api, "fetch"):
                transcript_list = api.fetch(video_id, languages=langs)
            elif hasattr(YouTubeTranscriptApi, "get_transcript"):
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        except Exception as e1:
            logger.debug(f"[{self.name}] Direct fetch failed: {e1}. Trying transcript discovery...")

        # 2. Discovery via list/list_transcripts if direct fetch didn't return data
        if not transcript_list:
            try:
                transcript_transcripts = None
                if hasattr(api, "list"):
                    transcript_transcripts = api.list(video_id)
                elif hasattr(YouTubeTranscriptApi, "list_transcripts"):
                    transcript_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)

                if transcript_transcripts:
                    try:
                        t = transcript_transcripts.find_transcript(langs)
                        transcript_list = t.fetch()
                        detected_lang = getattr(t, "language_code", langs[0])
                    except Exception:
                        for t in transcript_transcripts:
                            transcript_list = t.fetch()
                            detected_lang = getattr(t, "language_code", langs[0])
                            break
            except Exception as e2:
                logger.warning(f"[{self.name}] Discovery also failed for {video_id}: {e2}")

        if not transcript_list:
            logger.info(f"[{self.name}] No transcript data received for {video_id}")
            return None

        segments: List[TranscriptSegment] = []
        full_text_parts: List[str] = []

        for item in transcript_list:
            if isinstance(item, dict):
                text = item.get("text", "")
                start = float(item.get("start", 0.0))
                duration = float(item.get("duration", 0.0))
            else:
                text = getattr(item, "text", "")
                start = float(getattr(item, "start", 0.0))
                duration = float(getattr(item, "duration", 0.0))

            text = text.strip() if text else ""
            if not text:
                continue

            end = start + duration
            time_str = f"{format_timestamp(start)} – {format_timestamp(end)}"

            full_text_parts.append(text)
            segments.append(
                TranscriptSegment(
                    text=text,
                    start=start,
                    end=end,
                    timestamp_str=time_str
                )
            )

        if not segments:
            return None

        title = title_hint or f"YouTube Video ({video_id})"
        full_text = " ".join(full_text_parts)
        duration_sec = segments[-1].end if segments else None

        logger.info(f"[{self.name}] Successfully extracted {len(segments)} segments for video {video_id}")
        return TranscriptResult(
            video_id=video_id,
            title=title,
            channel=None,
            language=detected_lang,
            segments=segments,
            provider=self.name,
            full_text=full_text,
            duration_seconds=duration_sec
        )
