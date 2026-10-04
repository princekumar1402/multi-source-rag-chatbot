import re
from typing import List
from backend.app.services.ingestion.youtube.models import TranscriptSegment

def format_timestamp(seconds: float) -> str:
    """Converts seconds into HH:MM:SS or MM:SS format."""
    total_seconds = max(0, int(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def parse_time_str_to_seconds(time_str: str) -> float:
    """Parses 'HH:MM:SS.mmm' or 'MM:SS.mmm' into float seconds."""
    parts = time_str.strip().replace(",", ".").split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 1:
        return float(parts[0])
    return 0.0

def parse_json3_captions(json3_data: dict) -> List[TranscriptSegment]:
    """
    Parses native YouTube JSON3 caption track.
    Format:
    {
      "events": [
        {
          "tStartMs": 1200,
          "dDurationMs": 3400,
          "segs": [{"utf8": "hello"}, {"utf8": " world"}]
        }
      ]
    }
    """
    segments: List[TranscriptSegment] = []
    events = json3_data.get("events", [])

    for ev in events:
        segs = ev.get("segs", [])
        if not segs:
            continue
        text = "".join([s.get("utf8", "") for s in segs if s.get("utf8")]).strip()
        # Filter out empty or pure newline captions
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text == "\n":
            continue

        start_ms = ev.get("tStartMs", 0)
        dur_ms = ev.get("dDurationMs", 0)
        start_sec = max(0.0, float(start_ms) / 1000.0)
        end_sec = max(start_sec, (float(start_ms) + float(dur_ms)) / 1000.0)

        time_str = f"{format_timestamp(start_sec)} – {format_timestamp(end_sec)}"
        segments.append(
            TranscriptSegment(
                text=text,
                start=start_sec,
                end=end_sec,
                timestamp_str=time_str
            )
        )
    return segments

def parse_vtt_captions(vtt_content: str) -> List[TranscriptSegment]:
    """
    Parses standard WebVTT subtitles format with regex timestamp matching.
    """
    segments: List[TranscriptSegment] = []
    # Pattern for timestamp lines: 00:00:10.500 --> 00:00:14.200
    cue_pattern = re.compile(
        r"((?:\d{1,2}:)?\d{2}:\d{2}[\.,]\d{3})\s+-->\s+((?:\d{1,2}:)?\d{2}:\d{2}[\.,]\d{3})"
    )

    lines = vtt_content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = cue_pattern.search(line)
        if match:
            start_str, end_str = match.groups()
            start_sec = parse_time_str_to_seconds(start_str)
            end_sec = parse_time_str_to_seconds(end_str)

            # Collect subsequent text lines until empty line or next timestamp
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() and not cue_pattern.search(lines[i]):
                # Strip VTT formatting tags like <c> </c> <b> etc.
                cleaned = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if cleaned:
                    text_lines.append(cleaned)
                i += 1

            raw_text = " ".join(text_lines).strip()
            # Clean duplicate spaces or subtitle artifacts
            text = re.sub(r"\s+", " ", raw_text).strip()
            if text:
                time_str = f"{format_timestamp(start_sec)} – {format_timestamp(end_sec)}"
                segments.append(
                    TranscriptSegment(
                        text=text,
                        start=start_sec,
                        end=end_sec,
                        timestamp_str=time_str
                    )
                )
            continue
        i += 1

    return segments
