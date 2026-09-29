import os
from typing import Dict, Any, List, Optional

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.logging import logger

class TextLoader(BaseLoader):
    """
    Ingests plain text files (.txt) with robust encoding detection and paragraph preservation.
    """

    def __init__(self, file_path_or_bytes: str | bytes, file_name: Optional[str] = None):
        self.file_path_or_bytes = file_path_or_bytes
        self.file_name = file_name or (
            os.path.basename(file_path_or_bytes) if isinstance(file_path_or_bytes, str) else "document.txt"
        )

    def _read_text(self) -> str:
        if isinstance(self.file_path_or_bytes, bytes):
            raw_bytes = self.file_path_or_bytes
        else:
            with open(self.file_path_or_bytes, "rb") as f:
                raw_bytes = f.read()

        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "utf-16"]
        for enc in encodings:
            try:
                return raw_bytes.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue

        return raw_bytes.decode("utf-8", errors="replace")

    def load(self) -> ExtractedDocument:
        logger.info(f"Reading plain text file: {self.file_name}")
        content = self._read_text()

        if not content.strip():
            raise ValueError(f"Text file '{self.file_name}' is empty.")

        title = os.path.splitext(self.file_name)[0]
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [line.strip() for line in content.splitlines() if line.strip()]

        segments: List[ExtractedSegment] = [
            ExtractedSegment(text=para, section_title=title) for para in paragraphs
        ]

        return ExtractedDocument(
            title=title,
            source_type="txt",
            file_name=self.file_name,
            full_text=content,
            metadata={
                "file_name": self.file_name,
                "character_count": len(content),
                "paragraph_count": len(segments)
            },
            segments=segments
        )
