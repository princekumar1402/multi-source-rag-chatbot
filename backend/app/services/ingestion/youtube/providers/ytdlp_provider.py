import requests
from typing import List, Optional, Dict, Any

from backend.app.services.ingestion.youtube.providers.base import BaseYouTubeTranscriptProvider
from backend.app.services.ingestion.youtube.models import TranscriptResult, TranscriptSegment
from backend.app.services.ingestion.youtube.utils import parse_json3_captions, parse_vtt_captions
from backend.app.core.logging import logger

class YtDlpTranscriptProvider(BaseYouTubeTranscriptProvider):
    """
    Secondary subtitle/caption fallback provider using yt-dlp metadata extraction.
    Fetches official manual or auto-generated YouTube captions without downloading video or audio files.
    """

    @property
    def name(self) -> str:
        return "ytdlp_subtitles"

    def fetch_transcript(
        self,
        video_id: str,
        url: str,
        languages: Optional[List[str]] = None,
        title_hint: Optional[str] = None
    ) -> Optional[TranscriptResult]:
        langs = languages or ["en"]
        logger.info(f"[{self.name}] Attempting subtitle extraction for {video_id} using yt-dlp")

        try:
            import yt_dlp
        except ImportError:
            logger.warning(f"[{self.name}] yt-dlp is not installed. Skipping provider.")
            return None

        clean_url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        info: Optional[Dict[str, Any]] = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)
        except Exception as e:
            logger.warning(f"[{self.name}] yt-dlp failed to extract video info for {video_id}: {e}")
            return None

        if not info:
            return None

        title = info.get("title") or title_hint or f"YouTube Video ({video_id})"
        channel = info.get("uploader") or info.get("channel")
        duration = info.get("duration")

        subtitles = info.get("subtitles") or {}
        auto_captions = info.get("automatic_captions") or {}

        # 1. Identify best caption stream: prioritize manual subtitles in requested langs,
        # then auto_captions in requested langs, then any available subtitles.
        target_tracks = None
        selected_lang = langs[0]

        for lang in langs:
            if lang in subtitles and subtitles[lang]:
                target_tracks = subtitles[lang]
                selected_lang = lang
                logger.info(f"[{self.name}] Found manual subtitles in '{lang}'")
                break

        if not target_tracks:
            for lang in langs:
                if lang in auto_captions and auto_captions[lang]:
                    target_tracks = auto_captions[lang]
                    selected_lang = lang
                    logger.info(f"[{self.name}] Found automatic captions in '{lang}'")
                    break

        # Fallback to any language if requested not found
        if not target_tracks and subtitles:
            first_lang = next(iter(subtitles))
            target_tracks = subtitles[first_lang]
            selected_lang = first_lang
            logger.info(f"[{self.name}] Using fallback manual subtitles in '{first_lang}'")
        elif not target_tracks and auto_captions:
            first_lang = next(iter(auto_captions))
            target_tracks = auto_captions[first_lang]
            selected_lang = first_lang
            logger.info(f"[{self.name}] Using fallback automatic captions in '{first_lang}'")

        if not target_tracks:
            logger.info(f"[{self.name}] No subtitles or automatic captions found for {video_id}")
            return None

        # Prefer json3, then vtt
        selected_track = None
        for fmt in ["json3", "vtt"]:
            for track in target_tracks:
                if track.get("ext") == fmt:
                    selected_track = track
                    break
            if selected_track:
                break

        if not selected_track and target_tracks:
            selected_track = target_tracks[0]

        track_url = selected_track.get("url")
        track_ext = selected_track.get("ext", "vtt")

        if not track_url:
            logger.warning(f"[{self.name}] Selected track has no download URL")
            return None

        segments: List[TranscriptSegment] = []
        try:
            resp = requests.get(track_url, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"[{self.name}] Failed to fetch caption track: HTTP {resp.status_code}")
                return None

            if track_ext == "json3":
                segments = parse_json3_captions(resp.json())
            else:
                segments = parse_vtt_captions(resp.text)
        except Exception as parse_err:
            logger.warning(f"[{self.name}] Error downloading/parsing caption track ({track_ext}): {parse_err}")
            return None

        if not segments:
            logger.info(f"[{self.name}] Caption track contained zero parsed segments")
            return None

        full_text = " ".join([s.text for s in segments])
        duration_sec = duration or (segments[-1].end if segments else None)

        logger.info(f"[{self.name}] Successfully extracted {len(segments)} segments for video {video_id}")
        return TranscriptResult(
            video_id=video_id,
            title=title,
            channel=channel,
            language=selected_lang,
            segments=segments,
            provider=self.name,
            full_text=full_text,
            duration_seconds=duration_sec
        )
