import os
import uuid
import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session, sessionmaker

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

from backend.app.db.session import SessionLocal
from backend.app.models.document import Document
from backend.app.repositories.workspace_repo import WorkspaceRepository
from backend.app.repositories.document_repo import DocumentRepository
from backend.app.repositories.chunk_repo import ChunkRepository
from backend.app.repositories.ingestion_job_repo import IngestionJobRepository
from backend.app.services.rag.bm25 import BaseKeywordRetriever

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
    deduplication, metadata preservation, chunking, embedding, vector persistence,
    BM25 keyword index synchronization, and authoritative PostgreSQL persistence.
    """

    def __init__(
        self,
        embedder: BaseEmbedder,
        vector_store: BaseVectorStore,
        chunker: Optional[MetadataAwareChunker] = None,
        keyword_retriever: Optional[BaseKeywordRetriever] = None,
        session_factory: Optional[sessionmaker] = None
    ):
        self.embedder = embedder
        self.vector_store = vector_store
        self.chunker = chunker or MetadataAwareChunker()
        self.keyword_retriever = keyword_retriever
        self.session_factory = session_factory or SessionLocal

    @property
    def documents_db(self) -> Dict[str, DocumentResponse]:
        """Backward-compatibility view for any legacy component inspecting documents_db."""
        with self.session_factory() as db:
            docs = DocumentRepository.list_by_workspace(db, workspace_id="default", limit=1000)
            return {doc.id: self._doc_to_response(doc) for doc in docs}

    def _doc_to_response(self, doc: Document) -> DocumentResponse:
        """Converts an authoritative Document ORM model into a validated DocumentResponse schema."""
        return DocumentResponse(
            id=doc.id,
            title=doc.title,
            source_type=SourceType(doc.source_type),
            source_url=doc.source_url,
            file_name=doc.file_name,
            workspace_id=doc.workspace_id,
            doc_version=1,
            status=DocumentStatus(doc.status),
            content_hash=doc.content_hash,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            metadata=dict(doc.doc_metadata) if doc.doc_metadata else {}
        )

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

        with self.session_factory() as db:
            # Ensure workspace exists in PostgreSQL
            WorkspaceRepository.get_or_create(db, workspace_id=workspace_id)

            # Check for existing document in workspace with identical content hash
            existing = DocumentRepository.find_by_hash(db, workspace_id=workspace_id, content_hash=file_hash)
            if existing:
                logger.info(f"Duplicate document detected by file hash in DB: {existing.id} ('{existing.title}')")
                return self._doc_to_response(existing)

            doc_id = str(uuid.uuid4())
            doc_title = custom_title or os.path.splitext(file_name)[0]

            # 3. Create document record in PENDING status
            doc_record = DocumentRepository.create(
                db=db,
                workspace_id=workspace_id,
                source_type=source_type.value,
                title=doc_title,
                content_hash=file_hash,
                document_id=doc_id,
                file_name=file_name,
                status="pending",
                size_bytes=len(file_bytes),
                doc_metadata={"file_name": file_name, "file_size_bytes": len(file_bytes)}
            )

            # 4. Create IngestionJob record in PENDING status
            job = IngestionJobRepository.create(
                db=db,
                workspace_id=workspace_id,
                source_type=source_type.value,
                document_id=doc_id,
                status="pending"
            )

            # Transition to PROCESSING
            DocumentRepository.update_status(db, doc_id, status="processing")
            IngestionJobRepository.update_status(db, job.id, status="processing")
            db.commit()

            try:
                # 5. Extract content via specialized loader
                loader = self.get_loader_for_file(file_bytes, file_name, source_type)
                extracted: ExtractedDocument = loader.load()

                if custom_title:
                    extracted.title = custom_title

                # 6. Chunk with metadata preservation
                chunks = self.chunker.chunk_document(
                    doc=extracted,
                    document_id=doc_id,
                    workspace_id=workspace_id
                )

                if not chunks:
                    DocumentRepository.update_status(
                        db,
                        doc_id,
                        status="failed",
                        error_message="File produced zero extractable chunks."
                    )
                    IngestionJobRepository.update_status(
                        db,
                        job.id,
                        status="failed",
                        error_message="File produced zero extractable chunks."
                    )
                    db.commit()
                    return self._doc_to_response(DocumentRepository.get(db, doc_id))

                # 7. Persist chunks into PostgreSQL
                chunks_data = [
                    {
                        "id": c.chunk_id,
                        "document_id": doc_id,
                        "workspace_id": workspace_id,
                        "chunk_index": c.metadata.chunk_index,
                        "text": c.content,
                        "content_hash": compute_content_hash(c.content),
                        "source_type": c.metadata.source_type.value if hasattr(c.metadata.source_type, "value") else str(c.metadata.source_type),
                        "source_name": c.metadata.source_name,
                        "file_name": c.metadata.file_name,
                        "source_url": c.metadata.source_url,
                        "page_number": c.metadata.page_number,
                        "page_index": c.metadata.page_index,
                        "sheet_name": c.metadata.sheet_name,
                        "row_number": c.metadata.row_number,
                        "timestamp_str": c.metadata.timestamp_str,
                        "start_time": c.metadata.start_time,
                        "end_time": c.metadata.end_time,
                        "section_title": c.metadata.section_title,
                        "token_count": c.metadata.token_count
                    }
                    for c in chunks
                ]
                ChunkRepository.create_many(db, chunks_data)

                # 8. Generate embeddings
                chunk_texts = [c.content for c in chunks]
                embeddings = self.embedder.embed_documents(chunk_texts)

                # 9. Store chunks in vector store and keyword index
                self.vector_store.add_chunks(chunks=chunks, embeddings=embeddings)
                if self.keyword_retriever:
                    self.keyword_retriever.index_chunks(chunks)

                # 10. Mark READY and COMPLETED
                merged_meta = dict(doc_record.doc_metadata)
                merged_meta.update(extracted.metadata)
                updated_doc = DocumentRepository.update_status(
                    db,
                    doc_id,
                    status="ready",
                    chunk_count=len(chunks),
                    title=extracted.title,
                    metadata=merged_meta
                )
                IngestionJobRepository.update_status(db, job.id, status="completed")
                db.commit()
                logger.info(f"Successfully processed file '{file_name}': {len(chunks)} chunks indexed and persisted.")
                return self._doc_to_response(updated_doc)

            except Exception as e:
                logger.error(f"Error processing file '{file_name}': {e}")
                updated_doc = DocumentRepository.update_status(
                    db,
                    doc_id,
                    status="failed",
                    error_message=str(e)
                )
                IngestionJobRepository.update_status(
                    db,
                    job.id,
                    status="failed",
                    error_message=str(e)
                )
                db.commit()
                return self._doc_to_response(updated_doc)

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

        with self.session_factory() as db:
            # Ensure workspace exists
            WorkspaceRepository.get_or_create(db, workspace_id=workspace_id)

            # Check for existing document by hash or normalized URL
            existing = DocumentRepository.find_by_hash(db, workspace_id=workspace_id, content_hash=content_hash)
            if not existing and extracted.source_url:
                existing = DocumentRepository.find_by_url(db, workspace_id=workspace_id, source_url=extracted.source_url)

            if existing:
                logger.info(f"Duplicate document detected in DB: {existing.id} ({existing.title})")
                return self._doc_to_response(existing)

            doc_id = str(uuid.uuid4())

            # 3. Create Document record in PENDING status
            doc_record = DocumentRepository.create(
                db=db,
                workspace_id=workspace_id,
                source_type=extracted.source_type,
                title=extracted.title,
                content_hash=content_hash,
                document_id=doc_id,
                source_url=extracted.source_url,
                status="pending",
                doc_metadata=extracted.metadata
            )

            # 4. Create IngestionJob record
            job = IngestionJobRepository.create(
                db=db,
                workspace_id=workspace_id,
                source_type=extracted.source_type,
                document_id=doc_id,
                status="pending"
            )

            # Transition to PROCESSING
            DocumentRepository.update_status(db, doc_id, status="processing")
            IngestionJobRepository.update_status(db, job.id, status="processing")
            db.commit()

            try:
                # 5. Chunk document preserving metadata
                chunks = self.chunker.chunk_document(
                    doc=extracted,
                    document_id=doc_id,
                    workspace_id=workspace_id
                )

                if not chunks:
                    DocumentRepository.update_status(
                        db,
                        doc_id,
                        status="failed",
                        error_message="Document produced zero usable chunks."
                    )
                    IngestionJobRepository.update_status(
                        db,
                        job.id,
                        status="failed",
                        error_message="Document produced zero usable chunks."
                    )
                    db.commit()
                    return self._doc_to_response(DocumentRepository.get(db, doc_id))

                # 6. Persist chunks into PostgreSQL
                chunks_data = [
                    {
                        "id": c.chunk_id,
                        "document_id": doc_id,
                        "workspace_id": workspace_id,
                        "chunk_index": c.metadata.chunk_index,
                        "text": c.content,
                        "content_hash": compute_content_hash(c.content),
                        "source_type": c.metadata.source_type.value if hasattr(c.metadata.source_type, "value") else str(c.metadata.source_type),
                        "source_name": c.metadata.source_name,
                        "file_name": c.metadata.file_name,
                        "source_url": c.metadata.source_url,
                        "page_number": c.metadata.page_number,
                        "page_index": c.metadata.page_index,
                        "sheet_name": c.metadata.sheet_name,
                        "row_number": c.metadata.row_number,
                        "timestamp_str": c.metadata.timestamp_str,
                        "start_time": c.metadata.start_time,
                        "end_time": c.metadata.end_time,
                        "section_title": c.metadata.section_title,
                        "token_count": c.metadata.token_count
                    }
                    for c in chunks
                ]
                ChunkRepository.create_many(db, chunks_data)

                # 7. Generate embeddings in batch
                chunk_texts = [c.content for c in chunks]
                embeddings = self.embedder.embed_documents(chunk_texts)

                # 8. Store in persistent VectorStore and keyword index
                self.vector_store.add_chunks(chunks=chunks, embeddings=embeddings)
                if self.keyword_retriever:
                    self.keyword_retriever.index_chunks(chunks)

                # 9. Update status to READY
                updated_doc = DocumentRepository.update_status(
                    db,
                    doc_id,
                    status="ready",
                    chunk_count=len(chunks),
                    title=extracted.title,
                    metadata=extracted.metadata
                )
                IngestionJobRepository.update_status(db, job.id, status="completed")
                db.commit()
                logger.info(f"Successfully ingested '{doc_record.title}' with {len(chunks)} chunks.")
                return self._doc_to_response(updated_doc)

            except Exception as e:
                logger.error(f"Error during ingestion pipeline execution for {url}: {e}")
                updated_doc = DocumentRepository.update_status(
                    db,
                    doc_id,
                    status="failed",
                    error_message=str(e)
                )
                IngestionJobRepository.update_status(
                    db,
                    job.id,
                    status="failed",
                    error_message=str(e)
                )
                db.commit()
                return self._doc_to_response(updated_doc)

    def list_documents(self, workspace_id: str = "default") -> List[DocumentResponse]:
        """Queries PostgreSQL for all documents belonging to workspace_id."""
        with self.session_factory() as db:
            docs = DocumentRepository.list_by_workspace(db, workspace_id=workspace_id)
            return [self._doc_to_response(doc) for doc in docs]

    def get_document(self, document_id: str) -> Optional[DocumentResponse]:
        """Retrieves single document from PostgreSQL by document_id."""
        with self.session_factory() as db:
            doc = DocumentRepository.get(db, document_id)
            if not doc:
                return None
            return self._doc_to_response(doc)

    def delete_document(self, document_id: str) -> bool:
        """
        Purges document and chunks from:
        1. FAISS vector store
        2. BM25 keyword index
        3. PostgreSQL database (cascading chunks and jobs)
        """
        with self.session_factory() as db:
            doc = DocumentRepository.get(db, document_id)
            if not doc:
                return False

            # 1. Remove vectors from FAISS
            self.vector_store.delete_document(document_id)

            # 2. Remove tokens from BM25
            if self.keyword_retriever:
                self.keyword_retriever.remove_document(document_id)

            # 3. Delete PostgreSQL chunks and document
            ChunkRepository.delete_by_document(db, document_id)
            deleted = DocumentRepository.delete(db, document_id)
            db.commit()
            return deleted
