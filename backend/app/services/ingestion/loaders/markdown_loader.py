import os
import re
from typing import Dict, Any, List, Optional

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.logging import logger

class MarkdownLoader(BaseLoader):
    """
    Ingests Markdown files (.md) preserving heading hierarchy, code blocks, lists, and section titles.
    """

    def __init__(self, file_path_or_bytes: str | bytes, file_name: Optional[str] = None):
        self.file_path_or_bytes = file_path_or_bytes
        self.file_name = file_name or (
            os.path.basename(file_path_or_bytes) if isinstance(file_path_or_bytes, str) else "document.md"
        )

    def _read_text(self) -> str:
        if isinstance(self.file_path_or_bytes, bytes):
            return self.file_path_or_bytes.decode("utf-8", errors="replace")
        with open(self.file_path_or_bytes, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def load(self) -> ExtractedDocument:
        logger.info(f"Parsing Markdown file: {self.file_name}")
        content = self._read_text()

        if not content.strip():
            raise ValueError(f"Markdown file '{self.file_name}' is empty.")

        title = os.path.splitext(self.file_name)[0]
        # Look for first H1 tag as title if available
        first_h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if first_h1_match:
            title = first_h1_match.group(1).strip()

        lines = content.splitlines()
        segments: List[ExtractedSegment] = []
        current_section = title
        current_block: List[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()

            # Handle fenced code blocks
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                current_block.append(line)
                continue

            if in_code_block:
                current_block.append(line)
                continue

            # Detect headings (e.g. # H1, ## H2, ### H3)
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                # Flush previous block
                if current_block:
                    joined = "\n".join(current_block).strip()
                    if joined:
                        segments.append(ExtractedSegment(text=joined, section_title=current_section))
                    current_block = []

                current_section = heading_match.group(2).strip()
                current_block.append(stripped)
            elif not stripped:
                # Blank line represents paragraph boundary
                if current_block:
                    joined = "\n".join(current_block).strip()
                    if joined:
                        segments.append(ExtractedSegment(text=joined, section_title=current_section))
                    current_block = []
            else:
                current_block.append(line)

        # Flush remaining block
        if current_block:
            joined = "\n".join(current_block).strip()
            if joined:
                segments.append(ExtractedSegment(text=joined, section_title=current_section))

        if not segments:
            segments = [ExtractedSegment(text=content, section_title=title)]

        return ExtractedDocument(
            title=title,
            source_type="markdown",
            file_name=self.file_name,
            full_text=content,
            metadata={
                "file_name": self.file_name,
                "section_count": len(segments),
                "total_lines": len(lines)
            },
            segments=segments
        )
