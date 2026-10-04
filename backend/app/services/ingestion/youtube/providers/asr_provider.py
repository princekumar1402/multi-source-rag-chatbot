import os
import glob
import tempfile
from typing import List, Optional, Dict, Any

from backend.app.services.ingestion.youtube.providers.base import BaseYouTubeTranscriptProvider
from backend.app.services.ingestion.youtube.models import TranscriptResult, TranscriptSegment
from backend.app.services.ingestion.youtube.utils import format_timestamp
from backend.app.services.ingestion.youtube.exceptions import (
    ASRDisabledError,
    ASRDependencyMissingError,
    VideoDurationExceededError,
    AudioExtractionError
)
from backend.app.core.config import settings
from backend.app.core.logging import logger

class WhisperASRProvider(BaseYouTubeTranscriptProvider):
    """
    Tertiary fallback provider using Whisper-compatible local ASR.
    Only activates if explicitly enabled in configuration (YOUTUBE_ASR_ENABLED=True).
    Extracts audio-only, enforces max duration/size, transcribes, and strictly cleans up temp files.
    """

    @property
    def name(self) -> str:
        return "whisper_asr"

    def fetch_transcript(
        self,
        video_id: str,
        url: str,
        languages: Optional[List[str]] = None,
        title_hint: Optional[str] = None
    ) -> Optional[TranscriptResult]:
        if not getattr(settings, "YOUTUBE_ASR_ENABLED", False):
            logger.info(f"[{self.name}] ASR fallback is disabled in settings (YOUTUBE_ASR_ENABLED=False).")
            raise ASRDisabledError(
                "YouTube transcript/captions are unavailable, and local ASR fallback is disabled "
                "(YOUTUBE_ASR_ENABLED=False)."
            )

        logger.info(f"[{self.name}] Initiating audio-only transcription fallback for {video_id}")

        # Check dependencies
        try:
            import yt_dlp
        except ImportError:
            raise ASRDependencyMissingError("ASR audio extraction requires 'yt-dlp' to be installed.")

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ASRDependencyMissingError(
                "ASR transcription requires 'faster-whisper' to be installed. Please run: pip install faster-whisper"
            )

        clean_url = f"https://www.youtube.com/watch?v={video_id}"
        max_duration = getattr(settings, "YOUTUBE_MAX_DURATION_SECONDS", 1800)
        max_audio_mb = getattr(settings, "YOUTUBE_MAX_AUDIO_SIZE_MB", 50)
        max_bytes = max_audio_mb * 1024 * 1024
        model_name = getattr(settings, "YOUTUBE_ASR_MODEL", "tiny")

        # 1. Probe duration before downloading audio
        try:
            probe_opts = {"skip_download": True, "quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(probe_opts) as ydl:
                meta = ydl.extract_info(clean_url, download=False)
                duration = meta.get("duration")
                title = meta.get("title") or title_hint or f"YouTube Video ({video_id})"
                channel = meta.get("uploader") or meta.get("channel")

                if duration and duration > max_duration:
                    raise VideoDurationExceededError(
                        f"Video duration ({duration}s) exceeds maximum allowed limit of {max_duration}s for ASR."
                    )
        except VideoDurationExceededError:
            raise
        except Exception as e:
            logger.warning(f"[{self.name}] Probe failed for {video_id}: {e}")
            title = title_hint or f"YouTube Video ({video_id})"
            channel = None
            duration = None

        # 2. Extract audio into temporary directory with cleanup guarantee
        with tempfile.TemporaryDirectory(prefix="rag_yt_asr_") as temp_dir:
            out_pattern = os.path.join(temp_dir, f"{video_id}.%(ext)s")
            ydl_opts = {
                "format": "ba/b",
                "outtmpl": out_pattern,
                "max_filesize": max_bytes,
                "quiet": True,
                "no_warnings": True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([clean_url])
            except Exception as dl_err:
                raise AudioExtractionError(f"Failed to extract audio from video {video_id}: {dl_err}")

            # Locate downloaded audio file
            audio_files = glob.glob(os.path.join(temp_dir, f"{video_id}.*"))
            if not audio_files:
                raise AudioExtractionError(f"No audio file was produced for video {video_id}")

            audio_path = audio_files[0]
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            logger.info(f"[{self.name}] Audio extracted: {audio_path} ({file_size_mb:.2f} MB). Transcribing with '{model_name}'...")

            # 3. Transcribe audio with Whisper
            try:
                model = WhisperModel(model_name, device="cpu", compute_type="int8")
                whisper_segments, info = model.transcribe(audio_path, beam_size=1)

                segments: List[TranscriptSegment] = []
                full_text_parts: List[str] = []

                for seg in whisper_segments:
                    text = seg.text.strip()
                    if not text:
                        continue
                    start = float(seg.start)
                    end = float(seg.end)
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
                    raise AudioExtractionError(f"ASR produced zero transcript segments for video {video_id}")

                full_text = " ".join(full_text_parts)
                detected_lang = getattr(info, "language", "en")
                duration_sec = duration or (segments[-1].end if segments else None)

                logger.info(f"[{self.name}] ASR transcription successful: {len(segments)} segments extracted.")
                return TranscriptResult(
                    video_id=video_id,
                    title=title,
                    channel=channel,
                    language=detected_lang,
                    segments=segments,
                    provider=self.name,
                    full_text=full_text,
                    duration_seconds=duration_sec
                )
            except Exception as trans_err:
                if isinstance(trans_err, YouTubeIngestionError):
                    raise trans_err
                raise AudioExtractionError(f"ASR transcription failed for {video_id}: {trans_err}")
