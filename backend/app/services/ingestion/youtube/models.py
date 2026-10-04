from pydantic import BaseModel, Field
from typing import List, Optional

class TranscriptSegment(BaseModel):
    """Normalized segment representing a single timestamped sentence or caption line."""
    text: str
    start: float
    end: float
    timestamp_str: Optional[str] = None

class TranscriptResult(BaseModel):
    """Normalized output from any YouTube transcript provider in the fallback chain."""
    video_id: str
    title: str
    channel: Optional[str] = None
    language: str = "en"
    segments: List[TranscriptSegment] = Field(default_factory=list)
    provider: str
    full_text: str
    duration_seconds: Optional[float] = None
