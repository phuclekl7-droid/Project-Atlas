"""
Tests for Feature #33: PDF Page Preview.
"""

import io
from unittest.mock import MagicMock, patch

import pytest

from src.core.pdf_preview import (
    get_page_count,
    extract_page_text,
    extract_page_range,
    search_in_pdf,
    format_pdf_reference,
)


class TestGetPageCount:
    """Tests for get_page_count()."""

    def test_no_pypdf_installed(self):
        with patch("src.core.pdf_preview.PdfReader", None):
            count = get_page_count(b"fake bytes")
            assert count == 0

    def test_invalid_pdf(self):
        with patch("src.core.pdf_preview.PdfReader") as mock_reader:
            mock_reader.side_effect = ValueError("Invalid PDF")
            count = get_page_count(b"not a pdf")
            assert count == 0

    def test_success(self):
        mock_page = MagicMock()
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page, mock_page]
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader_instance):
            count = get_page_count(b"fake pdf")
            assert count == 2


class TestExtractPageText:
    """Tests for extract_page_text()."""

    def test_out_of_range_page(self):
        mock_page = MagicMock()
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader_instance):
            text = extract_page_text(b"fake", 5)
            assert text == ""

    def test_extract_text_success(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page content here"
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader_instance):
            text = extract_page_text(b"fake", 0)
            assert text == "Page content here"

    def test_text_truncated(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 5000
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader_instance):
            text = extract_page_text(b"fake", 0, max_chars=100)
            assert len(text) <= 100


class TestExtractPageRange:
    """Tests for extract_page_range()."""

    def test_range_success(self):
        pages = []
        for i in range(3):
            p = MagicMock()
            p.extract_text.return_value = f"Page {i} content"
            pages.append(p)

        mock_reader = MagicMock()
        mock_reader.pages = pages
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader):
            texts = extract_page_range(b"fake", 0, 2)
            assert len(texts) == 2
            assert texts[0] == "Page 0 content"
            assert texts[1] == "Page 1 content"

    def test_range_all_pages(self):
        pages = [MagicMock(), MagicMock()]
        for p in pages:
            p.extract_text.return_value = "content"
        mock_reader = MagicMock()
        mock_reader.pages = pages
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader):
            texts = extract_page_range(b"fake")
            assert len(texts) == 2


class TestSearchInPDF:
    """Tests for search_in_pdf()."""

    def test_keyword_found(self):
        pages = []
        p1 = MagicMock()
        p1.extract_text.return_value = "Introduction to Python"
        pages.append(p1)
        p2 = MagicMock()
        p2.extract_text.return_value = "Advanced topics in programming"
        pages.append(p2)

        mock_reader = MagicMock()
        mock_reader.pages = pages
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader):
            results = search_in_pdf(b"fake", "Python")
            assert len(results) == 1
            assert results[0]["page"] == 0

    def test_keyword_not_found(self):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Some other text"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        with patch("src.core.pdf_preview.PdfReader", return_value=mock_reader):
            results = search_in_pdf(b"fake", "Nonexistent")
            assert len(results) == 0


class TestFormatPdfReference:
    """Tests for format_pdf_reference()."""

    def test_basic(self):
        ref = format_pdf_reference("document.pdf")
        assert "document.pdf" in ref

    def test_with_page(self):
        ref = format_pdf_reference("doc.pdf", page_num=2)
        assert "doc.pdf" in ref
        assert "Page **3**" in ref  # 0-indexed to 1-indexed

    def test_with_snippet(self):
        ref = format_pdf_reference("doc.pdf", snippet="This is a quote from the PDF")
        assert "doc.pdf" in ref
        assert "quote" in ref
