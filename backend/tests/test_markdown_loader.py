import pytest
from backend.app.services.ingestion.loaders.markdown_loader import MarkdownLoader

def test_markdown_loader():
    md_content = """# Machine Learning Fundamentals

Machine learning is a subset of artificial intelligence focused on building applications that learn from data.

## Supervised Learning

Supervised learning algorithms are trained using labeled examples.

```python
from sklearn.linear_model import LogisticRegression
model = LogisticRegression()
```

### Key Algorithms
- Linear Regression
- Support Vector Machines
- Decision Trees
"""
    loader = MarkdownLoader(md_content.encode("utf-8"), file_name="ml_intro.md")
    doc = loader.load()

    assert doc.title == "Machine Learning Fundamentals"
    assert doc.source_type == "markdown"
    assert doc.file_name == "ml_intro.md"
    assert len(doc.segments) >= 2

    # Verify heading hierarchy and code block inclusion
    sections = [seg.section_title for seg in doc.segments]
    assert any("Supervised Learning" in s for s in sections if s)
    assert any("Key Algorithms" in s for s in sections if s)
    assert any("LogisticRegression" in seg.text for seg in doc.segments)

def test_markdown_empty_error():
    loader = MarkdownLoader(b"", file_name="empty.md")
    with pytest.raises(ValueError, match="is empty"):
        loader.load()
