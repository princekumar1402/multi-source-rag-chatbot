from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel

class ExtractedSegment(BaseModel):
    text: str
    page_number: int | None = None
    page_index: int | None = None
    sheet_name: str | None = None
    row_number: int | None = None
    start_time: float | None = None
    end_time: float | None = None
    timestamp_str: str | None = None
    section_title: str | None = None

class ExtractedDocument(BaseModel):
    title: str
    source_type: str
    source_url: str | None = None
    file_name: str | None = None
    full_text: str
    metadata: Dict[str, Any] = {}
    segments: List[ExtractedSegment] = []

class BaseLoader(ABC):
    """
    Abstract Base Class for all ingestion source loaders.
    Every loader extracts text content while preserving provenance metadata.
    """

    @abstractmethod
    def load(self) -> ExtractedDocument:
        """
        Execute document extraction and metadata harvesting.
        Returns an ExtractedDocument object.
        """
        pass
