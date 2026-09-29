import io
import os
from typing import Dict, Any, List, Optional
import docx

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.logging import logger

class DOCXLoader(BaseLoader):
    """
    Ingests Microsoft Word DOCX documents using python-docx.
    Preserves heading hierarchy, paragraphs, table rows, and document properties.
    """

    def __init__(self, file_path_or_bytes: str | bytes, file_name: Optional[str] = None):
        self.file_path_or_bytes = file_path_or_bytes
        self.file_name = file_name or (
            os.path.basename(file_path_or_bytes) if isinstance(file_path_or_bytes, str) else "document.docx"
        )

    def load(self) -> ExtractedDocument:
        logger.info(f"Extracting DOCX content from: {self.file_name}")

        try:
            if isinstance(self.file_path_or_bytes, bytes):
                doc = docx.Document(io.BytesIO(self.file_path_or_bytes))
            else:
                doc = docx.Document(self.file_path_or_bytes)
        except Exception as e:
            raise ValueError(f"Failed to open DOCX '{self.file_name}': {str(e)}")

        segments: List[ExtractedSegment] = []
        full_text_parts: List[str] = []

        # Extract core properties
        title = os.path.splitext(self.file_name)[0]
        try:
            if doc.core_properties.title:
                title = doc.core_properties.title.strip()
        except Exception:
            pass

        current_section = title

        # Iterate through paragraphs and detect headings
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue

            style_name = para.style.name.lower() if para.style else ""
            if "heading" in style_name or "title" in style_name:
                current_section = text

            full_text_parts.append(text)
            segments.append(
                ExtractedSegment(
                    text=text,
                    section_title=current_section
                )
            )

        # Extract tables
        for table_idx, table in enumerate(doc.tables, start=1):
            table_rows_text: List[str] = []
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells]
                # Filter empty rows
                if any(row_cells):
                    table_rows_text.append(" | ".join(row_cells))

            if table_rows_text:
                table_block = f"Table {table_idx}:\n" + "\n".join(table_rows_text)
                full_text_parts.append(table_block)
                segments.append(
                    ExtractedSegment(
                        text=table_block,
                        section_title=f"{current_section} (Table {table_idx})"
                    )
                )

        full_text = "\n\n".join(full_text_parts)
        if not full_text.strip():
            raise ValueError(f"DOCX document '{self.file_name}' contains no readable text or tables.")

        return ExtractedDocument(
            title=title,
            source_type="docx",
            file_name=self.file_name,
            full_text=full_text,
            metadata={
                "file_name": self.file_name,
                "paragraph_count": len(doc.paragraphs),
                "table_count": len(doc.tables),
                "author": doc.core_properties.author or ""
            },
            segments=segments
        )
