import os
import uuid
import datetime
from typing import Dict, Any, List, Optional

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument
from backend.app.services.ingestion.loaders.web_loader import WebLoader
from backend.app.services.ingestion.loaders.youtube_loader import YouTubeLoader
from backend.app.services.ingestion.loaders.pdf_loader import PDFLoader
from backend.app.services.ingestion.loaders.docx_loader import DOCXLoader
from backend.app.services.ingestion.loaders.txt_loader import TextLoader
from backend.app.services.ingestion.loaders.markdown_loader import MarkdownLoader
from backend.app.services.ingestion.loaders.csv_loader import CSVLoader
from backend.app.services.ingestion.loaders.xlsx_loader import XLSXLoader

from backend.app.services.ingestion.chunker import MetadataAwareChunker
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.services.vector_store.base import BaseVectorStore
from backend.app.schemas.document import DocumentResponse, DocumentStatus, SourceType
from backend.app.core.security import compute_content_hash, compute_file_hash, normalize_url
from backend.app.core.config import settings
from backend.app.core.logging import logger

SUPPORTED_FILE_EXTENSIONS = {
    ".pdf": SourceType.PDF,
    ".docx": SourceType.DOCX,
    ".txt": SourceType.TXT,
    ".md": SourceType.MARKDOWN,
    ".markdown": SourceType.MARKDOWN,
    ".csv": SourceType.CSV,
    ".xlsx": SourceType.XLSX,
}

class IngestionPipeline:
    """
    Coordinates multi-source extraction (Files, Web, YouTube),
    deduplication, metadata preservation, chunking, embedding, and vector persistence.
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
        # In-memory document registry for Phase 1 & 2 (migrated to PostgreSQL in Phase 4)
        self.documents_db: Dict[str, DocumentResponse] = {}

    def get_loader_for_url(self, url: str) -> BaseLoader:
        """Source detector that creates the appropriate web or video loader."""
        clean_url = url.strip().lower()
        if "youtube.com" in clean_url or "youtu.be" in clean_url:
            return YouTubeLoader(url)
        return WebLoader(url)

    def validate_file(self, file_bytes: bytes, file_name: str) -> SourceType:
        """
        Validates file size, extension, and content signatures.
        Rejects empty, oversized, unsupported, or suspicious files.
        """
        if not file_bytes or len(file_bytes) == 0:
            raise ValueError(f"Uploaded file '{file_name}' is empty.")

        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValueError(
                f"File size ({len(file_bytes) / (1024*1024):.2f} MB) exceeds maximum allowed "
                f"limit of {settings.MAX_FILE_SIZE_MB} MB."
            )

        _, ext = os.path.splitext(file_name.lower())
        if ext not in SUPPORTED_FILE_EXTENSIONS:
            allowed = ", ".join(SUPPORTED_FILE_EXTENSIONS.keys())
            raise ValueError(f"Unsupported file format '{ext}'. Allowed formats: {allowed}")

        source_type = SUPPORTED_FILE_EXTENSIONS[ext]

        # Content signature / magic byte inspection
        if source_type == SourceType.PDF:
            if not file_bytes.startswith(b"%PDF-"):
                raise ValueError(f"File '{file_name}' does not appear to be a valid PDF document.")
        elif source_type in (SourceType.DOCX, SourceType.XLSX):
            # Zip container signature (PK\x03\x04)
            if not file_bytes.startswith(b"PK\x03\x04"):
                raise ValueError(f"File '{file_name}' does not appear to be a valid {ext.upper()} archive.")

        return source_type

    def get_loader_for_file(self, file_bytes: bytes, file_name: str, source_type: SourceType) -> BaseLoader:
        """Instantiates the specialized loader for the verified file format."""
        if source_type == SourceType.PDF:
            return PDFLoader(file_bytes, file_name=file_name)
        elif source_type == SourceType.DOCX:
            return DOCXLoader(file_bytes, file_name=file_name)
        elif source_type == SourceType.TXT:
            return TextLoader(file_bytes, file_name=file_name)
        elif source_type == SourceType.MARKDOWN:
            return MarkdownLoader(file_bytes, file_name=file_name)
        elif source_type == SourceType.CSV:
            return CSVLoader(file_bytes, file_name=file_name)
        elif source_type == SourceType.XLSX:
            return XLSXLoader(file_bytes, file_name=file_name)
        else:
            raise ValueError(f"No registered loader for source type: {source_type}")

    def process_file(
        self,
        file_bytes: bytes,
        file_name: str,
        workspace_id: str = "default",
        custom_title: Optional[str] = None
    ) -> DocumentResponse:
        logger.info(f"Processing uploaded file: '{file_name}' ({len(file_bytes)} bytes) for workspace '{workspace_id}'")

        # 1. Validate file
        source_type = self.validate_file(file_bytes, file_name)

        # 2. Compute SHA-256 hash for deduplication
        file_hash = compute_file_hash(file_bytes)

        # Check for existing document in workspace with identical content hash
        for existing in self.documents_db.values():
            if existing.workspace_id == workspace_id and existing.content_hash == file_hash:
                logger.info(f"Duplicate document detected by file hash: {existing.id} ('{existing.title}')")
                return existing

        doc_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc)
        doc_title = custom_title or os.path.splitext(file_name)[0]

        # 3. Create document record
        doc_record = DocumentResponse(
            id=doc_id,
            title=doc_title,
            source_type=source_type,
            file_name=file_name,
            workspace_id=workspace_id,
            status=DocumentStatus.PROCESSING,
            content_hash=file_hash,
            chunk_count=0,
            created_at=now,
            updated_at=now,
            metadata={"file_name": file_name, "file_size_bytes": len(file_bytes)}
        )
        self.documents_db[doc_id] = doc_record

        try:
            # 4. Extract content via specialized loader
            loader = self.get_loader_for_file(file_bytes, file_name, source_type)
            extracted: ExtractedDocument = loader.load()

            if custom_title:
                extracted.title = custom_title
            doc_record.title = extracted.title
            doc_record.metadata.update(extracted.metadata)

            # 5. Chunk with metadata preservation
            chunks = self.chunker.chunk_document(
                doc=extracted,
                document_id=doc_id,
                workspace_id=workspace_id
            )

            if not chunks:
                doc_record.status = DocumentStatus.FAILED
                doc_record.error_message = "File produced zero extractable chunks."
                return doc_record

            # 6. Generate embeddings
            chunk_texts = [c.content for c in chunks]
            embeddings = self.embedder.embed_documents(chunk_texts)

            # 7. Store chunks in vector store
            self.vector_store.add_chunks(chunks=chunks, embeddings=embeddings)

            # 8. Mark ready
            doc_record.status = DocumentStatus.READY
            doc_record.chunk_count = len(chunks)
            doc_record.updated_at = datetime.datetime.now(datetime.timezone.utc)
            logger.info(f"Successfully processed file '{file_name}': {len(chunks)} chunks indexed.")
            return doc_record

        except Exception as e:
            logger.error(f"Error processing file '{file_name}': {e}")
            doc_record.status = DocumentStatus.FAILED
            doc_record.error_message = str(e)
            return doc_record

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
