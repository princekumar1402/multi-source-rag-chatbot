import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List

from backend.app.services.ingestion.loaders.base import BaseLoader, ExtractedDocument, ExtractedSegment
from backend.app.core.security import is_safe_url, normalize_url
from backend.app.core.logging import logger

class WebLoader(BaseLoader):
    """
    Robust web page and article scraper with SSRF protection and HTML boilerplate stripping.
    """

    def __init__(self, url: str):
        self.raw_url = url
        self.normalized_url = normalize_url(url)

    def load(self) -> ExtractedDocument:
        if not is_safe_url(self.normalized_url):
            raise ValueError(f"URL violates SSRF security policy: {self.raw_url}")

        logger.info(f"Fetching web page: {self.normalized_url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        try:
            response = requests.get(self.normalized_url, headers=headers, timeout=15)
            response.raise_for_status()
        except Exception as e:
            raise RuntimeError(f"Failed to fetch web content from {self.normalized_url}: {str(e)}")

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract title
        title = "Web Document"
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Decompose non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "svg", "form"]):
            element.decompose()

        # Extract structured sections
        segments: List[ExtractedSegment] = []
        headings = soup.find_all(["h1", "h2", "h3", "p"])
        current_section = title
        collected_paragraphs: List[str] = []

        for tag in headings:
            if tag.name in ["h1", "h2", "h3"]:
                heading_text = tag.get_text(strip=True)
                if heading_text:
                    current_section = heading_text
            elif tag.name == "p":
                para_text = tag.get_text(strip=True)
                if len(para_text) > 20: # Filter empty or tiny strings
                    collected_paragraphs.append(para_text)
                    segments.append(
                        ExtractedSegment(
                            text=para_text,
                            section_title=current_section
                        )
                    )

        full_text = "\n\n".join(collected_paragraphs)
        if not full_text:
            # Fallback to general text extraction if paragraph tags were sparse
            body_text = soup.get_text(separator="\n", strip=True)
            cleaned_lines = [line.strip() for line in body_text.splitlines() if len(line.strip()) > 30]
            full_text = "\n\n".join(cleaned_lines)
            if full_text:
                segments = [ExtractedSegment(text=full_text, section_title=title)]

        if not full_text:
            raise ValueError(f"No extractable text content found at URL: {self.normalized_url}")

        return ExtractedDocument(
            title=title,
            source_type="web",
            source_url=self.normalized_url,
            full_text=full_text,
            metadata={
                "url": self.normalized_url,
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", "")
            },
            segments=segments
        )
