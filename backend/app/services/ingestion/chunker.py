import uuid
from typing import List, Optional
from backend.app.services.ingestion.loaders.base import ExtractedDocument, ExtractedSegment
from backend.app.schemas.document import DocumentChunk, ChunkMetadata, SourceType
from backend.app.core.config import settings

class MetadataAwareChunker:
    """
    Intelligent chunker that preserves page numbers, sections, sheet names,
    row numbers, and video timestamp spans.
    """

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.DEFAULT_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.DEFAULT_CHUNK_OVERLAP

    def chunk_document(
        self,
        doc: ExtractedDocument,
        document_id: str,
        workspace_id: str = "default"
    ) -> List[DocumentChunk]:
        chunks: List[DocumentChunk] = []
        source_type = SourceType(doc.source_type)

        if not doc.segments:
            # Fallback if no segments provided: split raw full_text with character sliding window
            raw_text = doc.full_text
            start = 0
            index = 0
            while start < len(raw_text):
                end = min(start + self.chunk_size, len(raw_text))
                slice_text = raw_text[start:end].strip()
                if slice_text:
                    c_id = str(uuid.uuid4())
                    meta = ChunkMetadata(
                        chunk_id=c_id,
                        document_id=document_id,
                        workspace_id=workspace_id,
                        source_type=source_type,
                        source_name=doc.title,
                        file_name=doc.file_name,
                        source_url=doc.source_url,
                        chunk_index=index,
                        token_count=len(slice_text.split())
                    )
                    chunks.append(DocumentChunk(chunk_id=c_id, content=slice_text, metadata=meta))
                    index += 1
                if end >= len(raw_text):
                    break
                start += (self.chunk_size - self.chunk_overlap)
            return chunks

        # Structured segment aggregation
        current_text_parts: List[str] = []
        current_len = 0
        current_start_time: Optional[float] = None
        current_end_time: Optional[float] = None
        current_page: Optional[int] = None
        current_page_idx: Optional[int] = None
        current_sheet: Optional[str] = None
        current_row: Optional[int] = None
        current_section: Optional[str] = None
        chunk_index = 0

        for seg in doc.segments:
            seg_len = len(seg.text)
            
            boundary_changed = False
            if current_text_parts:
                if seg.page_number is not None and current_page is not None and seg.page_number != current_page:
                    boundary_changed = True
                elif seg.sheet_name is not None and current_sheet is not None and seg.sheet_name != current_sheet:
                    boundary_changed = True
                elif seg.row_number is not None and current_row is not None and seg.row_number != current_row:
                    boundary_changed = True

            if not current_text_parts:
                current_start_time = seg.start_time
                current_page = seg.page_number
                current_page_idx = seg.page_index
                current_sheet = seg.sheet_name
                current_row = seg.row_number
                current_section = seg.section_title

            if (boundary_changed or (current_len + seg_len > self.chunk_size)) and current_text_parts:
                # Flush current accumulator into a chunk
                joined_text = " ".join(current_text_parts).strip()
                if joined_text:
                    c_id = str(uuid.uuid4())
                    time_str = None
                    if current_start_time is not None and current_end_time is not None:
                        from backend.app.services.ingestion.loaders.youtube_loader import format_timestamp
                        time_str = f"{format_timestamp(current_start_time)} – {format_timestamp(current_end_time)}"

                    meta = ChunkMetadata(
                        chunk_id=c_id,
                        document_id=document_id,
                        workspace_id=workspace_id,
                        source_type=source_type,
                        source_name=doc.title,
                        file_name=doc.file_name,
                        source_url=doc.source_url,
                        page_number=current_page,
                        page_index=current_page_idx,
                        sheet_name=current_sheet,
                        row_number=current_row,
                        start_time=current_start_time,
                        end_time=current_end_time,
                        timestamp_str=time_str,
                        section_title=current_section,
                        chunk_index=chunk_index,
                        token_count=len(joined_text.split())
                    )
                    chunks.append(DocumentChunk(chunk_id=c_id, content=joined_text, metadata=meta))
                    chunk_index += 1

                # Reset accumulator
                current_text_parts = [seg.text]
                current_len = seg_len
                current_start_time = seg.start_time
                current_end_time = seg.end_time
                current_page = seg.page_number
                current_page_idx = seg.page_index
                current_sheet = seg.sheet_name
                current_row = seg.row_number
                current_section = seg.section_title
            else:
                current_text_parts.append(seg.text)
                current_len += seg_len
                current_end_time = seg.end_time if seg.end_time is not None else current_end_time
                if not current_section and seg.section_title:
                    current_section = seg.section_title

        # Final flush
        if current_text_parts:
            joined_text = " ".join(current_text_parts).strip()
            if joined_text:
                c_id = str(uuid.uuid4())
                time_str = None
                if current_start_time is not None and current_end_time is not None:
                    from backend.app.services.ingestion.loaders.youtube_loader import format_timestamp
                    time_str = f"{format_timestamp(current_start_time)} – {format_timestamp(current_end_time)}"

                meta = ChunkMetadata(
                    chunk_id=c_id,
                    document_id=document_id,
                    workspace_id=workspace_id,
                    source_type=source_type,
                    source_name=doc.title,
                    file_name=doc.file_name,
                    source_url=doc.source_url,
                    page_number=current_page,
                    page_index=current_page_idx,
                    sheet_name=current_sheet,
                    row_number=current_row,
                    start_time=current_start_time,
                    end_time=current_end_time,
                    timestamp_str=time_str,
                    section_title=current_section,
                    chunk_index=chunk_index,
                    token_count=len(joined_text.split())
                )
                chunks.append(DocumentChunk(chunk_id=c_id, content=joined_text, metadata=meta))

        return chunks
