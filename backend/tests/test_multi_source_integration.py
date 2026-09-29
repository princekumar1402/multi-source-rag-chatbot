import io
import pytest
import pymupdf
import docx
import openpyxl

from backend.app.services.ingestion.pipeline import IngestionPipeline
from backend.app.services.embeddings.huggingface import HuggingFaceEmbedder
from backend.app.services.vector_store.faiss_store import FAISSVectorStore
from backend.app.services.rag.retriever import DenseRetrieverWithReranker
from backend.app.services.rag.engine import RAGEngine
from backend.app.services.llm.base import BaseLLM
from backend.app.schemas.rag import RAGQueryRequest
from backend.app.schemas.document import SourceType, DocumentStatus
from typing import Optional, Iterator

class GroundedMockLLM(BaseLLM):
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        # Mock answers verifying citation formatting based on context
        if "deadlock" in prompt.lower():
            return "Deadlock requires circular wait and mutual exclusion [Source 1]."
        elif "rahul" in prompt.lower():
            return "Rahul is in the CSE department with a CGPA of 8.4 [Source 1]."
        elif "alex" in prompt.lower():
            return "Alex Chen has a GPA of 3.9 majoring in Computer Science [Source 1]."
        return "Based on the sources, the information is provided accurately [Source 1]."

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Iterator[str]:
        yield self.generate(prompt)

def test_multi_source_coexistence_and_citations(tmp_path):
    # 1. Setup shared unified pipeline
    embedder = HuggingFaceEmbedder()
    store = FAISSVectorStore(dimension=embedder.dimension, store_dir=str(tmp_path / "vs"))
    pipeline = IngestionPipeline(embedder=embedder, vector_store=store)

    retriever = DenseRetrieverWithReranker(embedder=embedder, vector_store=store, min_relevance_threshold=0.01)
    rag_engine = RAGEngine(retriever=retriever, llm=GroundedMockLLM())

    workspace_id = "multi_source_ws"

    # --- Ingest PDF ---
    pdf_doc = pymupdf.open()
    p1 = pdf_doc.new_page()
    p1.insert_text((50, 50), "Operating Systems principles and concepts.")
    p2 = pdf_doc.new_page()
    p2.insert_text((50, 50), "Deadlock occurs when four conditions are met: mutual exclusion, hold and wait, no preemption, and circular wait.")
    pdf_doc.set_metadata({"title": "Operating Systems Notes"})
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()
    d_pdf = pipeline.process_file(pdf_bytes, "os_notes.pdf", workspace_id=workspace_id)
    assert d_pdf.status == DocumentStatus.READY

    # --- Ingest DOCX ---
    d_docx_file = docx.Document()
    d_docx_file.add_heading("Database Indexing", level=1)
    d_docx_file.add_paragraph("B-Trees and Hash indexes provide fast logarithmic search times.")
    buf_docx = io.BytesIO()
    d_docx_file.save(buf_docx)
    d_docx = pipeline.process_file(buf_docx.getvalue(), "dbms.docx", workspace_id=workspace_id)
    assert d_docx.status == DocumentStatus.READY

    # --- Ingest TXT ---
    txt_content = b"Computer Networks: TCP is connection-oriented and guarantees delivery with 3-way handshakes."
    d_txt = pipeline.process_file(txt_content, "cn_notes.txt", workspace_id=workspace_id)
    assert d_txt.status == DocumentStatus.READY

    # --- Ingest Markdown ---
    md_content = b"# Microservices Architecture\n\nMicroservices break down monolithic apps into loosely coupled services."
    d_md = pipeline.process_file(md_content, "architecture.md", workspace_id=workspace_id)
    assert d_md.status == DocumentStatus.READY

    # --- Ingest CSV ---
    csv_content = b"Name,Department,CGPA\nRahul,CSE,8.4\nSneha,ECE,9.0\n"
    d_csv = pipeline.process_file(csv_content, "students.csv", workspace_id=workspace_id)
    assert d_csv.status == DocumentStatus.READY

    # --- Ingest XLSX ---
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Honors"
    ws.append(["Student ID", "Full Name", "Major", "GPA"])
    ws.append(["CS99", "Alex Chen", "Computer Science", 3.9])
    buf_xlsx = io.BytesIO()
    wb.save(buf_xlsx)
    wb.close()
    d_xlsx = pipeline.process_file(buf_xlsx.getvalue(), "honors.xlsx", workspace_id=workspace_id)
    assert d_xlsx.status == DocumentStatus.READY

    # Total documents ingested
    docs = pipeline.list_documents(workspace_id=workspace_id)
    assert len(docs) == 6

    # Verify all source types coexist in the vector index
    total_vectors = store.count(workspace_id=workspace_id)
    assert total_vectors >= 6

    # --- Test 1: Query PDF & Verify Page Number Citation ---
    query_pdf = RAGQueryRequest(question="What causes a deadlock in operating systems?", workspace_id=workspace_id)
    resp_pdf = rag_engine.query(query_pdf)
    assert resp_pdf.has_sufficient_context is True
    assert len(resp_pdf.citations) > 0
    pdf_citation = next((c for c in resp_pdf.citations if c.source_type == SourceType.PDF and "deadlock" in c.snippet.lower()), None)
    assert pdf_citation is not None
    assert pdf_citation.page_number == 2
    assert pdf_citation.file_name == "os_notes.pdf"

    # --- Test 2: Query CSV & Verify Row Number Citation ---
    query_csv = RAGQueryRequest(question="What is Rahul's CGPA and department in CSE?", workspace_id=workspace_id)
    resp_csv = rag_engine.query(query_csv)
    assert resp_csv.has_sufficient_context is True
    csv_citation = next((c for c in resp_csv.citations if c.source_type == SourceType.CSV), None)
    assert csv_citation is not None
    assert csv_citation.row_number == 2

    # --- Test 3: Query XLSX & Verify Sheet Name & Row Citation ---
    query_xlsx = RAGQueryRequest(question="What is Alex Chen's GPA in honors?", workspace_id=workspace_id)
    resp_xlsx = rag_engine.query(query_xlsx)
    assert resp_xlsx.has_sufficient_context is True
    xlsx_citation = next((c for c in resp_xlsx.citations if c.source_type == SourceType.XLSX), None)
    assert xlsx_citation is not None
    assert xlsx_citation.sheet_name == "Honors"

    # --- Test 4: Document Deletion Purge Verification ---
    assert pipeline.delete_document(d_pdf.id) is True
    after_delete_docs = pipeline.list_documents(workspace_id=workspace_id)
    assert len(after_delete_docs) == 5
    assert store.count(workspace_id=workspace_id) < total_vectors

    # Ensure deleted PDF can no longer be retrieved
    results_after_delete = store.search(embedder.embed_query("deadlock"), top_k=5, filters={"document_ids": [d_pdf.id]})
    assert len(results_after_delete) == 0
