import os
from typing import Dict, Any, List, Optional
import pymupdf

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.logging import logger

class PDFLoader(BaseLoader):
    """
    Production-quality PDF extractor using PyMuPDF.
    Preserves page numbers (1-indexed), page indices, document metadata, and detects scanned/empty documents.
    """

    def __init__(self, file_path_or_bytes: str | bytes, file_name: Optional[str] = None):
        self.file_path_or_bytes = file_path_or_bytes
        self.file_name = file_name or (
            os.path.basename(file_path_or_bytes) if isinstance(file_path_or_bytes, str) else "uploaded_document.pdf"
        )

    def load(self) -> ExtractedDocument:
        logger.info(f"Extracting PDF content from: {self.file_name}")

        try:
            if isinstance(self.file_path_or_bytes, bytes):
                doc = pymupdf.open(stream=self.file_path_or_bytes, filetype="pdf")
            else:
                doc = pymupdf.open(self.file_path_or_bytes)
        except Exception as e:
            raise ValueError(f"Failed to open PDF '{self.file_name}': {str(e)}")

        try:
            total_pages = len(doc)
            if total_pages == 0:
                raise ValueError(f"PDF '{self.file_name}' contains zero pages.")

            # Extract PDF metadata
            meta = doc.metadata or {}
            title = meta.get("title") or os.path.splitext(self.file_name)[0]
            if not title.strip():
                title = os.path.splitext(self.file_name)[0]

            segments: List[ExtractedSegment] = []
            full_text_parts: List[str] = []
            total_extracted_chars = 0

            for page_idx in range(total_pages):
                page = doc[page_idx]
                page_no = page_idx + 1
                page_text = page.get_text("text").strip()

                if not page_text:
                    continue

                total_extracted_chars += len(page_text)
                full_text_parts.append(page_text)

                # Split page into meaningful paragraphs
                raw_paragraphs = [p.strip() for p in page_text.split("\n\n") if len(p.strip()) > 10]
                if not raw_paragraphs:
                    raw_paragraphs = [line.strip() for line in page_text.splitlines() if len(line.strip()) > 15]

                for para in raw_paragraphs:
                    segments.append(
                        ExtractedSegment(
                            text=para,
                            page_number=page_no,
                            page_index=page_idx,
                            section_title=f"Page {page_no}"
                        )
                    )

            if total_extracted_chars == 0:
                raise ValueError(
                    f"PDF '{self.file_name}' contains no extractable text. "
                    "The document may be scanned or image-based, which requires OCR processing."
                )

            return ExtractedDocument(
                title=title,
                source_type="pdf",
                file_name=self.file_name,
                full_text="\n\n".join(full_text_parts),
                metadata={
                    "file_name": self.file_name,
                    "total_pages": total_pages,
                    "author": meta.get("author", ""),
                    "creator": meta.get("creator", ""),
                    "producer": meta.get("producer", ""),
                },
                segments=segments
            )
        finally:
            doc.close()
