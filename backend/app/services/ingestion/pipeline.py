import uuid
import datetime
from typing import Dict, Any, List, Optional

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument
from backend.app.services.ingestion.loaders.web_loader import WebLoader
from backend.app.services.ingestion.loaders.youtube_loader import YouTubeLoader
from backend.app.services.ingestion.chunker import MetadataAwareChunker
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.schemas.document import DocumentResponse, DocumentStatus, SourceType
from backend.app.core.security import compute_content_hash, normalize_url
from backend.app.core.logging import logger

class IngestionPipeline:
    """
    Coordinates extraction, deduplication, chunking, embedding, and vector persistence.
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        chunker: Optional[MetadataAwareChunker] = None
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.chunker = chunker or MetadataAwareChunker()
        # In-memory document registry for Phase 1 (migrated to PostgreSQL in Phase 4)
        self.documents_db: Dict[str, DocumentResponse] = {}

    def get_loader_for_url(self, url: str) -> BaseLoader:
        """Source detector that creates the appropriate loader."""
        clean_url = url.strip().lower()
        if "youtube.com" in clean_url or "youtu.be" in clean_url:
            return YouTubeLoader(url)
        return WebLoader(url)

    def process_url(
        self,
        url: str,
        workspace_id: str = "default",
        custom_title: Optional[str] = None
    ) -> DocumentResponse:
        logger.info(f"Ingesting URL: {url} into workspace: {workspace_id}")
        
        # 1. Instantiate loader
        loader = self.get_loader_for_url(url)
        extracted: ExtractedDocument = loader.load()

        if custom_title:
            extracted.title = custom_title

        # 2. Content hash for deduplication
        content_hash = compute_content_hash(extracted.full_text)

        # Check for existing document in workspace with same hash or normalized URL
        for existing in self.documents_db.values():
            if existing.workspace_id == workspace_id:
                if existing.content_hash == content_hash:
                    logger.info(f"Duplicate document detected by content hash: {existing.id} ({existing.title})")
                    return existing
                if existing.source_url and normalize_url(existing.source_url) == normalize_url(extracted.source_url or ""):
                    logger.info(f"Duplicate document detected by URL: {existing.id}")
                    return existing

        doc_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)

        # 3. Create document record
        doc_record = DocumentResponse(
            id=doc_id,
            title=extracted.title,
            source_type=SourceType(extracted.source_type),
            source_url=extracted.source_url,
            workspace_id=workspace_id,
            status=DocumentStatus.PROCESSING,
            content_hash=content_hash,
            chunk_count=0,
            created_at=now,
            updated_at=now,
            metadata=extracted.metadata
        )
        self.documents_db[doc_id] = doc_record

        try:
            # 4. Chunk document preserving metadata
            chunks = self.chunker.chunk_document(
                doc=extracted,
                document_id=doc_id,
                workspace_id=workspace_id
            )

            if not chunks:
                doc_record.status = DocumentStatus.FAILED
                doc_record.error_message = "Document produced zero usable chunks."
                return doc_record

            # 5. Generate embeddings in batch
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embedder.embed_documents(chunk_texts)

            # 6. Store in persistent VectorStore
            self.vector_store.add_chunks(chunks=chunks, embeddings=embeddings)

            # 7. Update status to READY
            doc_record.status = DocumentStatus.READY
            doc_record.chunk_count = len(chunks)
            doc_record.updated_at = datetime.datetime.now(datetime.timezone.utc)
            logger.info(f"Successfully ingested '{doc_record.title}' with {len(chunks)} chunks.")
            return doc_record

        except Exception as e:
            logger.error(f"Error during ingestion pipeline execution for {url}: {e}")
            doc_record.status = DocumentStatus.FAILED
            doc_record.error_message = str(e)
            return doc_record

    def list_documents(self, workspace_id: str = "default") -> List[DocumentResponse]:
        return [doc for doc in self.documents_db.values() if doc.workspace_id == workspace_id]

    def get_document(self, document_id: str) -> Optional[DocumentResponse]:
        return self.documents_db.get(document_id)

    def delete_document(self, document_id: str) -> bool:
        if document_id in self.documents_db:
            del self.documents_db[document_id]
            self.vector_store.delete_document(document_id)
            return True
        return False
