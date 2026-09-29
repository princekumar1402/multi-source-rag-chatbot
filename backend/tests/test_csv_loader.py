import pytest
from backend.app.services.ingestion.loaders.csv_loader import CSVLoader

def test_csv_loader():
    csv_content = """Name,Department,CGPA,Year
Rahul,CSE,8.4,3
Ananya,ECE,9.1,4
Vikram,Mechanical,7.8,2
"""
    loader = CSVLoader(csv_content.encode("utf-8"), file_name="students.csv")
    doc = loader.load()

    assert doc.title == "students"
    assert doc.source_type == "csv"
    assert doc.file_name == "students.csv"
    assert len(doc.segments) == 3

    # Verify row numbers
    row_numbers = [seg.row_number for seg in doc.segments]
    assert row_numbers == [2, 3, 4]

    # Verify structured key-value formatting
    first_seg = doc.segments[0]
    assert "Name: Rahul" in first_seg.text
    assert "Department: CSE" in first_seg.text
    assert "CGPA: 8.4" in first_seg.text

def test_csv_loader_empty_error():
    loader = CSVLoader(b"Name,Age\n", file_name="no_data.csv")
    with pytest.raises(ValueError, match="zero data rows"):
        loader.load()
