class YouTubeIngestionError(Exception):
    """Base exception for all YouTube ingestion errors."""
    pass

class InvalidYouTubeURLError(YouTubeIngestionError):
    """Raised when the URL is malformed or no valid video ID could be extracted."""
    pass

class VideoUnavailableError(YouTubeIngestionError):
    """Raised when the video is deleted, private, geo-restricted, or does not exist."""
    pass

class TranscriptUnavailableError(YouTubeIngestionError):
    """Raised when no transcripts or captions could be retrieved."""
    pass

class CaptionsDisabledError(TranscriptUnavailableError):
    """Raised when captions/transcripts are explicitly disabled by the video creator."""
    pass

class VideoDurationExceededError(YouTubeIngestionError):
    """Raised when the video duration exceeds the configured safety maximum."""
    pass

class ASRDisabledError(YouTubeIngestionError):
    """Raised when transcription fails and ASR fallback is disabled."""
    pass

class ASRDependencyMissingError(YouTubeIngestionError):
    """Raised when ASR is enabled but required dependencies (e.g. faster-whisper) are not installed."""
    pass

class AudioExtractionError(YouTubeIngestionError):
    """Raised when audio download or conversion fails during ASR fallback."""
    pass

class NetworkFailureError(YouTubeIngestionError):
    """Raised when network requests to YouTube or providers time out or fail."""
    pass
