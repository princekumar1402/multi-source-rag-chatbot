import pytest
from backend.app.core.security import normalize_url, compute_content_hash, is_safe_url

def test_normalize_url():
    url1 = "https://example.com/article/?utm_source=twitter&utm_medium=social&ref=123"
    url2 = "HTTPS://EXAMPLE.COM/article"
    assert normalize_url(url1) == "https://example.com/article"
    assert normalize_url(url2) == "https://example.com/article"

def test_compute_content_hash():
    text1 = "This is a test document text."
    text2 = "This is a test document text."
    text3 = "Different text content."
    assert compute_content_hash(text1) == compute_content_hash(text2)
    assert compute_content_hash(text1) != compute_content_hash(text3)

def test_is_safe_url_ssrf():
    # Should block dangerous localhost and private IPs
    assert not is_safe_url("http://localhost:8000/secret")
    assert not is_safe_url("http://127.0.0.1:8000/admin")
    assert not is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert not is_safe_url("http://192.168.1.1/router")
    assert not is_safe_url("file:///etc/passwd")
    assert not is_safe_url("ftp://example.com")

    # Should allow valid public web URLs
    assert is_safe_url("https://en.wikipedia.org/wiki/Artificial_intelligence")
    assert is_safe_url("https://docs.python.org/3/")
