from typing import List, Tuple, Dict, Any, Optional, Set
from backend.app.schemas.document import DocumentChunk
from backend.app.core.logging import logger

class ContextualChunkExpander:
    """
    Parent/Child Contextual Chunk Expander:
    Expands high-relevance child chunks with neighboring context windows
    from the same parent document, preserving 100% document scope and citation provenance.
    """

    def __init__(self, max_expansion_window: int = 1):
        self.max_expansion_window = max_expansion_window

    def expand_context(
        self,
        retrieved: List[Tuple[DocumentChunk, float]],
        document_chunks: Dict[str, List[DocumentChunk]],
        allowed_doc_ids: Optional[List[str]] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        For each retrieved chunk, if neighboring chunks exist in document_chunks for that document,
        assembles expanded context while preserving the primary chunk's ID, source, and citations.
        """
        if not retrieved or not document_chunks:
            return retrieved

        allowed_set = set(allowed_doc_ids) if allowed_doc_ids else None
        expanded: List[Tuple[DocumentChunk, float]] = []

        for chunk, score in retrieved:
            doc_id = chunk.metadata.document_id
            if allowed_set and doc_id not in allowed_set:
                continue

            doc_all_chunks = document_chunks.get(doc_id, [])
            if not doc_all_chunks or len(doc_all_chunks) <= 1:
                expanded.append((chunk, score))
                continue

            # Locate position of chunk within document
            pos = -1
            for idx, c in enumerate(doc_all_chunks):
                if c.chunk_id == chunk.chunk_id:
                    pos = idx
                    break

            if pos == -1:
                expanded.append((chunk, score))
                continue

            # Gather neighbor chunks within expansion window
            start_idx = max(0, pos - self.max_expansion_window)
            end_idx = min(len(doc_all_chunks), pos + self.max_expansion_window + 1)
            neighbors = doc_all_chunks[start_idx:end_idx]

            if len(neighbors) == 1:
                expanded.append((chunk, score))
            else:
                # Merge content while keeping primary chunk's metadata and chunk_id intact
                merged_content = "\n\n".join([c.content for c in neighbors])
                expanded_chunk = DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    content=merged_content,
                    metadata=chunk.metadata
                )
                expanded.append((expanded_chunk, score))

        return expanded
