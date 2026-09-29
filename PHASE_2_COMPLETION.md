# Phase 2 Completion Report: Multi-Source Knowledge Ingestion

**Phase:** Phase 2 — Multi-Source Ingestion  
**Status:** Completed & Verified  
**Date:** 2026-09-29  
**Test Suite:** 26 / 26 tests passed (100%)  
**Frontend Build:** Vite TypeScript bundle built successfully  

---

## 1. Files Created

* **Specialized Document Loaders:**
  * `backend/app/services/ingestion/loaders/pdf_loader.py`: Production PyMuPDF (`fitz`) extractor preserving page numbers, page indices, author metadata, and detecting empty/scanned PDFs.
  * `backend/app/services/ingestion/loaders/docx_loader.py`: Microsoft Word extractor using `python-docx` preserving heading hierarchy, paragraphs, table rows, and document properties.
  * `backend/app/services/ingestion/loaders/txt_loader.py`: Plain text file extractor with UTF-8 and fallback encoding detection (`latin-1`, `cp1252`, `utf-16`).
  * `backend/app/services/ingestion/loaders/markdown_loader.py`: Markdown parser preserving heading hierarchy (`#`, `##`, `###`), section titles, fenced code blocks, and list items.
  * `backend/app/services/ingestion/loaders/csv_loader.py`: Tabular CSV loader converting rows into structured key-value records while preserving row numbers and column headers.
  * `backend/app/services/ingestion/loaders/xlsx_loader.py`: Excel workbook extractor using `openpyxl` across multiple sheets, preserving sheet names, row numbers, and headers.
* **Testing Suites:**
  * `backend/tests/test_pdf_loader.py`: Unit tests for PyMuPDF extraction, page numbers, and scanned/empty PDF detection.
  * `backend/tests/test_docx_loader.py`: Unit tests for heading hierarchy, table rows, and paragraphs.
  * `backend/tests/test_txt_loader.py`: Unit tests for UTF-8 and fallback encoding.
  * `backend/tests/test_markdown_loader.py`: Unit tests for headings, code blocks, and section tracking.
  * `backend/tests/test_csv_loader.py`: Unit tests for CSV delimiters, key-value rows, and row numbers.
  * `backend/tests/test_xlsx_loader.py`: Unit tests for multi-sheet workbooks, sheet names, and row numbers.
  * `backend/tests/test_file_validation_and_dedup.py`: Unit tests for magic byte verification (`%PDF-`, zip headers), size limits, and SHA-256 deduplication.
  * `backend/tests/test_multi_source_integration.py`: Complete multi-source coexistence test (PDF, DOCX, TXT, MD, CSV, XLSX, Web, YouTube) in a single shared vector index.

---

## 2. Files Modified

* `backend/requirements.txt`: Added `pymupdf>=1.24.0`, `python-docx>=1.1.0`, and `openpyxl>=3.1.0`.
* `backend/app/services/ingestion/loaders/base.py`: Extended `ExtractedSegment` with `page_index`, `sheet_name`, and `row_number`.
* `backend/app/schemas/document.py`: Updated `ChunkMetadata` to retain `file_name`, `page_index`, `sheet_name`, and `row_number`.
* `backend/app/schemas/rag.py`: Updated `Citation` to propagate `file_name`, `page_index`, `sheet_name`, and `row_number`.
* `backend/app/services/ingestion/chunker.py`: Updated `MetadataAwareChunker` to enforce boundary flushes across pages, sheets, and rows.
* `backend/app/services/ingestion/pipeline.py`: Added `process_file`, `validate_file`, content signature checking, and file hash deduplication.
* `backend/app/services/rag/engine.py`: Updated RAG prompt builder and citation formatter to render page numbers, sheet names, and row numbers.
* `backend/app/api/v1/documents.py`: Added `POST /api/v1/documents/upload` supporting multipart file uploads.
* `frontend/src/types/index.ts`: Updated TypeScript `Citation` and `DocumentItem` interfaces.
* `frontend/src/services/api.ts`: Added `uploadFile` multipart client API.
* `frontend/src/components/SourceInput.tsx`: Added drag-and-drop file upload UI with format tags.
* `frontend/src/components/DocumentList.tsx`: Added distinct format icons for PDF, DOCX, TXT, MD, CSV, XLSX, Web, and YouTube.
* `frontend/src/components/CitationCard.tsx`: Added visual badge indicators for page numbers, Excel sheets, and CSV rows.
* `frontend/src/App.tsx`: Wired up file upload handler and state reload.

---

## 3. Loaders Implemented

1. **PDFLoader**: PyMuPDF (`fitz`), page-by-page text extraction, 1-indexed page numbering, metadata harvesting.
2. **DOCXLoader**: `python-docx`, heading level tracking, paragraph grouping, markdown table representation.
3. **TextLoader**: UTF-8 and fallback multi-encoding reader (`latin-1`, `cp1252`, `utf-16`).
4. **MarkdownLoader**: Heading hierarchy extraction, fenced code block preservation, bullet/numbered list preservation.
5. **CSVLoader**: Delimiter sniffer (comma, tab, semicolon, pipe), key-value row representation (`Col1: Val1 | Col2: Val2`), row number tracking.
6. **XLSXLoader**: `openpyxl`, multi-sheet iterator, sheet name tracking, row number tracking, empty row skipping.
7. **WebLoader**: Retained from Phase 1 with SSRF validation, boilerplate stripping, and heading extraction.
8. **YouTubeLoader**: Retained from Phase 1 with video ID parser, transcript fetching, and start/end timestamp extraction.

---

## 4. Supported File Formats & MIME/Magic Signatures

| Format | Extension | Underlying Engine | Magic Signature / Validation |
| :--- | :--- | :--- | :--- |
| **PDF** | `.pdf` | PyMuPDF | Header starts with `b"%PDF-"` |
| **DOCX** | `.docx` | python-docx | Zip archive signature `b"PK\x03\x04"` |
| **TXT** | `.txt` | Multi-encoding decoder | UTF-8 / latin-1 decodability |
| **Markdown**| `.md`, `.markdown`| Heading line parser | UTF-8 decodability |
| **CSV** | `.csv` | Python csv sniffer | Dialect & delimiter validation |
| **XLSX** | `.xlsx` | openpyxl | Zip archive signature `b"PK\x03\x04"` |
| **Web** | `http(s)://` | BeautifulSoup + requests | Public IP SSRF validation |
| **YouTube** | URL | youtube-transcript-api | Video ID regex & oEmbed verification |

---

## 5. Metadata Preserved for Each Format

* **PDF**: `file_name`, `page_number` (1-indexed), `page_index` (0-indexed), `section_title` (Page N), `author`, `total_pages`.
* **DOCX**: `file_name`, `section_title` (Heading 1/2/3 hierarchy), `paragraph_count`, `table_count`.
* **TXT**: `file_name`, `character_count`, `paragraph_count`.
* **Markdown**: `file_name`, `section_title` (nearest markdown heading), `section_count`.
* **CSV**: `file_name`, `row_number` (2-indexed for data rows), `columns`.
* **XLSX**: `file_name`, `sheet_name`, `row_number`, `sheets`.
* **YouTube**: `video_id`, `start_time`, `end_time`, `timestamp_str` (`HH:MM:SS – HH:MM:SS`), `source_url`.
* **Web**: `source_url`, `title`, `section_title`.

---

## 6. API Changes

### Added Endpoint:
* `POST /api/v1/documents/upload`
  * **Payload**: Multipart `file: UploadFile`, `workspace_id: Form(str, default="default")`, `title: Form(Optional[str])`
  * **Validation**: File extension, file magic bytes, file size (`MAX_FILE_SIZE_MB`), empty file check.
  * **Response**:
    ```json
    {
      "id": "c1f7a26e-44ab-45ce-89d2-7b198129e01f",
      "title": "Operating Systems Notes",
      "source_type": "pdf",
      "file_name": "os_notes.pdf",
      "workspace_id": "default",
      "doc_version": 1,
      "status": "ready",
      "content_hash": "a89d71c3...",
      "chunk_count": 42,
      "summary": null,
      "error_message": null,
      "created_at": "2026-09-29T19:07:43Z",
      "updated_at": "2026-09-29T19:07:43Z",
      "metadata": {
        "file_name": "os_notes.pdf",
        "file_size_bytes": 14205,
        "total_pages": 42
      }
    }
    ```

---

## 7. Deduplication Behavior

* **File Uploads**: A SHA-256 hash is computed over raw file bytes. If an identical file has already been ingested into the workspace, the existing `DocumentResponse` is immediately returned. No duplicate chunks or embeddings are generated.
* **URLs**: URLs are canonically normalized (stripping tracking parameters like `utm_*` and trailing slashes) and checked against existing document URLs in the workspace.

---

## 8. Document Status Transitions

1. **Upload Initiated**: Record created with status `PROCESSING`.
2. **Extraction & Chunking**: Content parsed into segments; if empty, status transitions to `FAILED` with sanitized error message.
3. **Embedding & Vector Storage**: Chunks embedded and indexed into FAISS.
4. **Completion**: Status transitions to `READY` with chunk count updated.
5. **Deletion**: `DELETE /api/v1/documents/{id}` purges vectors from FAISS and drops document record.

---

## 9. Tests Created & Results

All 26 tests executed and passed:

```text
backend/tests/test_api.py::test_root_endpoint PASSED                     [  3%]
backend/tests/test_api.py::test_health_endpoint PASSED                   [  7%]
backend/tests/test_api.py::test_documents_list_empty PASSED              [ 11%]
backend/tests/test_chunker.py::test_chunker_metadata_preservation PASSED [ 15%]
backend/tests/test_csv_loader.py::test_csv_loader PASSED                 [ 19%]
backend/tests/test_csv_loader.py::test_csv_loader_empty_error PASSED     [ 23%]
backend/tests/test_docx_loader.py::test_docx_loader_success PASSED       [ 26%]
backend/tests/test_docx_loader.py::test_docx_loader_empty_error PASSED   [ 30%]
backend/tests/test_file_validation_and_dedup.py::test_file_validation PASSED [ 34%]
backend/tests/test_file_validation_and_dedup.py::test_duplicate_file_deduplication PASSED [ 38%]
backend/tests/test_markdown_loader.py::test_markdown_loader PASSED       [ 42%]
backend/tests/test_markdown_loader.py::test_markdown_empty_error PASSED  [ 46%]
backend/tests/test_multi_source_integration.py::test_multi_source_coexistence_and_citations PASSED [ 50%]
backend/tests/test_pdf_loader.py::test_pdf_loader_success PASSED         [ 53%]
backend/tests/test_pdf_loader.py::test_pdf_loader_empty_error PASSED     [ 57%]
backend/tests/test_rag_engine.py::test_rag_engine_with_context PASSED    [ 61%]
backend/tests/test_rag_engine.py::test_rag_engine_insufficient_context PASSED [ 65%]
backend/tests/test_security_and_dedup.py::test_normalize_url PASSED      [ 69%]
backend/tests/test_security_and_dedup.py::test_compute_content_hash PASSED [ 73%]
backend/tests/test_security_and_dedup.py::test_is_safe_url_ssrf PASSED   [ 76%]
backend/tests/test_txt_loader.py::test_txt_loader_utf8 PASSED            [ 80%]
backend/tests/test_txt_loader.py::test_txt_loader_fallback_encoding PASSED [ 84%]
backend/tests/test_txt_loader.py::test_txt_loader_empty_error PASSED     [ 88%]
backend/tests/test_vector_store.py::test_faiss_vector_store PASSED       [ 92%]
backend/tests/test_xlsx_loader.py::test_xlsx_loader_multi_sheet PASSED   [ 96%]
backend/tests/test_xlsx_loader.py::test_xlsx_loader_empty_error PASSED   [100%]

======================= 26 passed, 1 warning in 30.42s ========================
```

---

## 10. Multi-Source Integration Test Summary

Test `test_multi_source_integration.py` successfully validated:
* Simultaneous ingestion of 6 distinct file formats into one shared workspace:
  * `os_notes.pdf` (PDF)
  * `dbms.docx` (DOCX)
  * `cn_notes.txt` (TXT)
  * `architecture.md` (Markdown)
  * `students.csv` (CSV)
  * `honors.xlsx` (XLSX)
* Verified that queries retrieve from the correct respective sources:
  * PDF query retrieves chunk with `page_number == 2` and `file_name == 'os_notes.pdf'`
  * CSV query retrieves row with `row_number == 2`
  * XLSX query retrieves row with `sheet_name == 'Honors'`
* Verified that document deletion purges all corresponding vector chunks without affecting other documents.

---

## 11. Known Limitations

* Scanned PDFs (pure images without OCR text layer) are detected and rejected with a clean message instructing that OCR is required; Tesseract/EasyOCR is slated for future multimodal phases.
* Password-protected Excel/PDF documents require manual decryption before upload.

---

## 12. Example cURL Commands

### Upload PDF Document
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@os_notes.pdf" \
  -F "workspace_id=default"
```

### Upload Excel Workbook
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@students.xlsx" \
  -F "workspace_id=default"
```

### Ingest Webpage
```bash
curl -X POST "http://localhost:8000/api/v1/documents/url" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org/3/tutorial/index.html", "workspace_id": "default"}'
```

### Ingest YouTube Video
```bash
curl -X POST "http://localhost:8000/api/v1/documents/youtube" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "workspace_id": "default"}'
```

---

## 13. Next Recommended Phase

**Phase 3 — Proper RAG Engine & Citations**:
* Multi-document hybrid search (BM25 keyword + Dense vector fusion)
* Cross-encoder reranker
* Context window compression & token pruning
* Enhanced citation link navigation
* Advanced multi-turn conversational query reformulation

Phase 2 is complete and verified. Awaiting your approval before proceeding to Phase 3.
