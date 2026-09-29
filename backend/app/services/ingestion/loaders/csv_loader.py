import csv
import io
import os
from typing import Dict, Any, List, Optional

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.logging import logger

class CSVLoader(BaseLoader):
    """
    Ingests tabular CSV data, transforming rows into semantically descriptive key-value records.
    Preserves row numbers and column headers.
    """

    def __init__(self, file_path_or_bytes: str | bytes, file_name: Optional[str] = None):
        self.file_path_or_bytes = file_path_or_bytes
        self.file_name = file_name or (
            os.path.basename(file_path_or_bytes) if isinstance(file_path_or_bytes, str) else "data.csv"
        )

    def _get_string_io(self) -> io.StringIO:
        if isinstance(self.file_path_or_bytes, bytes):
            raw = self.file_path_or_bytes.decode("utf-8", errors="replace")
        else:
            with open(self.file_path_or_bytes, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        return io.StringIO(raw)

    def load(self) -> ExtractedDocument:
        logger.info(f"Parsing CSV file: {self.file_name}")
        stream = self._get_string_io()
        sample = stream.read(2048)
        stream.seek(0)

        if not sample.strip():
            raise ValueError(f"CSV file '{self.file_name}' is empty.")

        # Detect delimiter
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except Exception:
            dialect = csv.excel

        reader = csv.reader(stream, dialect)
        rows = list(reader)

        if not rows:
            raise ValueError(f"CSV file '{self.file_name}' contains no rows.")

        headers = [h.strip() for h in rows[0]]
        title = os.path.splitext(self.file_name)[0]
        segments: List[ExtractedSegment] = []
        full_text_parts: List[str] = []

        # Process each row (row 1 was headers, so data starts at row 2)
        for row_idx, row in enumerate(rows[1:], start=2):
            # Skip empty rows
            if not any(cell.strip() for cell in row):
                continue

            record_parts = []
            for col_idx, cell_value in enumerate(row):
                val = cell_value.strip()
                if not val:
                    continue
                header_name = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx+1}"
                record_parts.append(f"{header_name}: {val}")

            if record_parts:
                row_text = f"Row {row_idx}: " + " | ".join(record_parts)
                full_text_parts.append(row_text)
                segments.append(
                    ExtractedSegment(
                        text=row_text,
                        row_number=row_idx,
                        section_title=f"{title} (Row {row_idx})"
                    )
                )

        if not segments:
            raise ValueError(f"CSV file '{self.file_name}' has headers but zero data rows.")

        return ExtractedDocument(
            title=title,
            source_type="csv",
            file_name=self.file_name,
            full_text="\n".join(full_text_parts),
            metadata={
                "file_name": self.file_name,
                "columns": headers,
                "total_rows": len(segments)
            },
            segments=segments
        )
