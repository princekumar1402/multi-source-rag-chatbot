import pytest
import pymupdf
from backend.app.services.ingestion.loaders.pdf_loader import PDFLoader

def create_sample_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    # Page 1
    p1 = doc.new_page()
    p1.insert_text((50, 50), "Chapter 1: Operating Systems Overview.\nA computer system consists of hardware, OS, and applications.")
    # Page 2
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Chapter 2: Deadlocks and Concurrency.\nDeadlock occurs when processes wait indefinitely for resources held by each other.")
    doc.set_metadata({"title": "Operating Systems Course Notes", "author": "Professor Smith"})
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes

def test_pdf_loader_success():
    pdf_bytes = create_sample_pdf_bytes()
    loader = PDFLoader(pdf_bytes, file_name="os_course.pdf")
    doc = loader.load()

    assert doc.title == "Operating Systems Course Notes"
    assert doc.source_type == "pdf"
    assert doc.file_name == "os_course.pdf"
    assert len(doc.segments) >= 2

    # Check page 1 and page 2 metadata
    page_numbers = [seg.page_number for seg in doc.segments]
    assert 1 in page_numbers
    assert 2 in page_numbers

    # Verify content accuracy
    assert any("Deadlocks" in seg.text and seg.page_number == 2 for seg in doc.segments)

def test_pdf_loader_empty_error():
    doc = pymupdf.open()
    doc.new_page() # Blank page
    pdf_bytes = doc.tobytes()
    doc.close()

    loader = PDFLoader(pdf_bytes, file_name="empty.pdf")
    with pytest.raises(ValueError, match="no extractable text"):
        loader.load()
