import hashlib
import ipaddress
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def normalize_url(raw_url: str) -> str:
    """
    Normalizes a URL to ensure canonical representation for deduplication.
    - Strips whitespace
    - Lowercases scheme and netloc
    - Strips tracking query parameters (utm_*, ref, etc.)
    - Removes trailing slashes from path
    """
    url = raw_url.strip()
    parsed = urlparse(url)
    
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Filter tracking params
    ignored_params = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid"}
    query_tuples = parse_qsl(parsed.query, keep_blank_values=False)
    filtered_query = [(k, v) for k, v in query_tuples if k.lower() not in ignored_params]
    
    # Sort query parameters for consistency
    filtered_query.sort(key=lambda x: x[0])
    new_query = urlencode(filtered_query)
    
    # Normalize path
    path = parsed.path
    if path.endswith("/") and len(path) > 1:
        path = path.rstrip("/")
        
    return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))

def compute_content_hash(content: str) -> str:
    """Computes a SHA-256 hash of text content for deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def compute_file_hash(file_bytes: bytes) -> str:
    """Computes a SHA-256 hash of raw file bytes for deduplication."""
    return hashlib.sha256(file_bytes).hexdigest()

def is_safe_url(url: str) -> bool:
    """
    Validates URL to protect against SSRF (Server-Side Request Forgery).
    Blocks private IP ranges, localhost, AWS metadata IPs, and non-http(s) schemes.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        # Block localhost explicitly
        if hostname.lower() in ("localhost", "127.0.0.1", "::1"):
            return False

        # Try to resolve IP and check if it's private or reserved
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
            ):
                return False
        except ValueError:
            # Hostname is a domain name, not a raw IP
            pass

        return True
    except Exception:
        return False
