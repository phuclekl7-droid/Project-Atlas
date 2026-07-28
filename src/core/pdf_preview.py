"""
PDF Page Preview (Feature #33).
Extracts text from specific PDF pages for preview in the UI.

Provides:
- extract_page_text(pdf_bytes, page_num) -> str
- extract_page_range(pdf_bytes, start, end) -> list[str]
- get_page_count(pdf_bytes) -> int
- format_pdf_reference(filename, page_num, text) -> str
"""

import io
from typing import Optional

from src.core import setup_logger

logger = setup_logger("pdf_preview")

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


def _ensure_reader(file_bytes: bytes):
    """Get a PdfReader instance from bytes, or raise ImportError/ValueError."""
    if PdfReader is None:
        raise ImportError("pypdf is not installed. Run: pip install pypdf")
    try:
        return PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {e}")


def get_page_count(file_bytes: bytes) -> int:
    """Get the total number of pages in a PDF."""
    try:
        reader = _ensure_reader(file_bytes)
        return len(reader.pages)
    except (ImportError, ValueError) as e:
        logger.warning(f"Cannot get page count: {e}")
        return 0


def extract_page_text(file_bytes: bytes, page_num: int, max_chars: int = 2000) -> str:
    """
    Extract text from a single PDF page.

    Args:
        file_bytes: Raw PDF file bytes
        page_num: 0-indexed page number
        max_chars: Maximum characters to return

    Returns:
        Extracted text, or empty string on error
    """
    try:
        reader = _ensure_reader(file_bytes)
        if page_num < 0 or page_num >= len(reader.pages):
            logger.warning(f"Page {page_num} out of range (0-{len(reader.pages) - 1})")
            return ""

        page = reader.pages[page_num]
        text = page.extract_text() or ""
        return text[:max_chars]
    except Exception as e:
        logger.warning(f"Failed to extract page {page_num}: {e}")
        return ""


def extract_page_range(
    file_bytes: bytes,
    start_page: int = 0,
    end_page: Optional[int] = None,
    max_chars_per_page: int = 2000,
) -> list[str]:
    """
    Extract text from a range of PDF pages.

    Args:
        file_bytes: Raw PDF file bytes
        start_page: 0-indexed start page
        end_page: Exclusive end page (None = last page)
        max_chars_per_page: Max chars per page

    Returns:
        List of page texts
    """
    try:
        reader = _ensure_reader(file_bytes)
        total = len(reader.pages)
        end = end_page or total
        start = max(0, start_page)
        end = min(end, total)

        pages = []
        for i in range(start, end):
            page = reader.pages[i]
            text = (page.extract_text() or "")[:max_chars_per_page]
            pages.append(text)
        return pages
    except Exception as e:
        logger.warning(f"Failed to extract page range: {e}")
        return []


def search_in_pdf(file_bytes: bytes, keyword: str) -> list[dict]:
    """
    Search for a keyword across all PDF pages.

    Returns:
        List of {"page": int, "snippet": str} matches
    """
    results = []
    try:
        reader = _ensure_reader(file_bytes)
        keyword_lower = keyword.lower()

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if keyword_lower in text.lower():
                # Find context around keyword
                idx = text.lower().find(keyword_lower)
                start = max(0, idx - 80)
                end = min(len(text), idx + len(keyword) + 80)
                snippet = text[start:end].strip()
                results.append({"page": i, "snippet": snippet})
    except Exception as e:
        logger.warning(f"PDF search failed: {e}")

    return results


def format_pdf_reference(
    filename: str,
    page_num: Optional[int] = None,
    snippet: Optional[str] = None,
) -> str:
    """Format a PDF source reference for display in chat."""
    parts = [f"📄 **Source:** `{filename}`"]
    if page_num is not None:
        parts.append(f"📍 Page **{page_num + 1}**")
    if snippet:
        parts.append(f"\n> {snippet[:200]}")
    return "\n".join(parts)
