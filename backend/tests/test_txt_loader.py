import pytest
from backend.app.services.ingestion.loaders.txt_loader import TextLoader

def test_txt_loader_utf8():
    content = "First paragraph about distributed systems.\n\nSecond paragraph discussing Paxos and Raft consensus protocols."
    loader = TextLoader(content.encode("utf-8"), file_name="consensus.txt")
    doc = loader.load()

    assert doc.title == "consensus"
    assert doc.source_type == "txt"
    assert doc.file_name == "consensus.txt"
    assert len(doc.segments) == 2
    assert "Paxos" in doc.segments[1].text

def test_txt_loader_fallback_encoding():
    # Text encoded with latin-1 containing non-ascii characters
    content = "Café au lait and naïve algorithms.\n\nResume with résumé."
    latin1_bytes = content.encode("latin-1")

    loader = TextLoader(latin1_bytes, file_name="french_notes.txt")
    doc = loader.load()

    assert doc.source_type == "txt"
    assert "Café" in doc.full_text

def test_txt_loader_empty_error():
    loader = TextLoader(b"   \n\n  ", file_name="blank.txt")
    with pytest.raises(ValueError, match="is empty"):
        loader.load()
