""""
Unit tests for file extraction functions in the knowledge module.

Tests:
- extract_text_from_pdf() with mocked pypdf
- extract_text_from_docx() with mocked python-docx
- extract_text_from_file() dispatching by extension
- add_file() on ChromaDBKnowledgeBase (mocked ChromaDB)
- add_file() on SimpleKnowledgeBase
- Error handling (missing libraries, corrupt files)
- SUPPORTED_EXTENSIONS
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge import (
    KnowledgeDoc,
    SUPPORTED_EXTENSIONS,
    SearchResult,
    SimpleKnowledgeBase,
    chunk_text,
    extract_text_from_docx,
    extract_text_from_file,
    extract_text_from_pdf,
)


# ============================================================
# SUPPORTED_EXTENSIONS Tests
# ============================================================


class TestSupportedExtensions:
    def test_includes_txt(self):
        assert ".txt" in SUPPORTED_EXTENSIONS

    def test_includes_pdf(self):
        assert ".pdf" in SUPPORTED_EXTENSIONS

    def test_includes_docx(self):
        assert ".docx" in SUPPORTED_EXTENSIONS

    def test_all_have_descriptions(self):
        for ext, desc in SUPPORTED_EXTENSIONS.items():
            assert isinstance(ext, str)
            assert ext.startswith(".")
            assert isinstance(desc, str)
            assert len(desc) > 0


# ============================================================
# extract_text_from_pdf Tests
# ============================================================


class TestExtractPDF:
    def test_extract_single_page(self):
        """Should extract text from a single-page PDF."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello from PDF!"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.knowledge.PdfReader", return_value=mock_reader):
            text = extract_text_from_pdf(b"fake-pdf-bytes")

        assert text == "Hello from PDF!"

    def test_extract_multi_page(self):
        """Should extract and join text from multiple pages."""
        pages = []
        for i in range(3):
            p = MagicMock()
            p.extract_text.return_value = f"Page {i + 1} content"
            pages.append(p)

        mock_reader = MagicMock()
        mock_reader.pages = pages

        with patch("src.knowledge.PdfReader", return_value=mock_reader):
            text = extract_text_from_pdf(b"fake-pdf-bytes")

        assert "Page 1 content" in text
        assert "Page 2 content" in text
        assert "Page 3 content" in text

    def test_extract_empty_pages_skipped(self):
        """Pages with no text should be skipped."""
        p1 = MagicMock()
        p1.extract_text.return_value = "Page 1"
        p2 = MagicMock()
        p2.extract_text.return_value = ""  # Empty page

        mock_reader = MagicMock()
        mock_reader.pages = [p1, p2]

        with patch("src.knowledge.PdfReader", return_value=mock_reader):
            text = extract_text_from_pdf(b"fake-pdf-bytes")

        assert text == "Page 1"

    def test_extract_no_text(self):
        """PDF with no extractable text should return empty string."""
        p = MagicMock()
        p.extract_text.return_value = ""

        mock_reader = MagicMock()
        mock_reader.pages = [p]

        with patch("src.knowledge.PdfReader", return_value=mock_reader):
            text = extract_text_from_pdf(b"fake-pdf-bytes")

        assert text == ""

    def test_missing_pypdf_returns_empty(self):
        """When pypdf is not installed, should return empty string."""
        with patch("src.knowledge.PdfReader", side_effect=ImportError("No module named 'pypdf'")):
            text = extract_text_from_pdf(b"fake-pdf-bytes")
        assert text == ""

    def test_corrupt_pdf_returns_empty(self):
        """Corrupt PDF should return empty string."""
        with patch("src.knowledge.PdfReader", side_effect=Exception("PDF file is corrupted")):
            text = extract_text_from_pdf(b"garbage-data")
        assert text == ""


# ============================================================
# extract_text_from_docx Tests
# ============================================================


class TestExtractDOCX:
    def test_extract_simple(self):
        """Should extract text from a DOCX with paragraphs."""
        para1 = MagicMock()
        para1.text = "Hello from DOCX!"
        para2 = MagicMock()
        para2.text = "Second paragraph."

        mock_doc = MagicMock()
        mock_doc.paragraphs = [para1, para2]

        with patch("src.knowledge.Document", return_value=mock_doc):
            text = extract_text_from_docx(b"fake-docx-bytes")

        assert "Hello from DOCX!" in text
        assert "Second paragraph." in text

    def test_extract_skips_empty_paragraphs(self):
        """Empty paragraphs should be skipped."""
        p1 = MagicMock()
        p1.text = "Non-empty"
        p2 = MagicMock()
        p2.text = ""  # Empty
        p3 = MagicMock()
        p3.text = "   "  # Whitespace only (strip removes it)

        mock_doc = MagicMock()
        mock_doc.paragraphs = [p1, p2, p3]

        with patch("src.knowledge.Document", return_value=mock_doc):
            text = extract_text_from_docx(b"fake-docx-bytes")

        assert "Non-empty" in text
        assert "" not in text.split("\n\n")  # No empty paragraphs

    def test_extract_no_paragraphs(self):
        """DOCX with no paragraphs should return empty string."""
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        with patch("src.knowledge.Document", return_value=mock_doc):
            text = extract_text_from_docx(b"fake-docx-bytes")

        assert text == ""

    def test_missing_python_docx_returns_empty(self):
        """When python-docx is not installed, should return empty string."""
        with patch("src.knowledge.Document", side_effect=ImportError("No module named 'docx'")):
            text = extract_text_from_docx(b"fake-docx-bytes")
        assert text == ""

    def test_corrupt_docx_returns_empty(self):
        """Corrupt DOCX should return empty string."""
        with patch("src.knowledge.Document", side_effect=Exception("Bad DOCX file")):
            text = extract_text_from_docx(b"garbage-data")
        assert text == ""


# ============================================================
# extract_text_from_file Tests
# ============================================================


class TestExtractFromFile:
    def test_txt_utf8(self):
        """Should decode .txt files as UTF-8."""
        text = extract_text_from_file("hello.txt", "Xin chào! 🎉".encode("utf-8"))
        assert text == "Xin chào! 🎉"

    def test_txt_latin1_fallback(self):
        """Should fall back to latin-1 if UTF-8 fails."""
        # Latin-1 encoded text (e.g., résumé)
        text = extract_text_from_file("resume.txt", "Résumé".encode("latin-1"))
        assert "Résumé" in text

    def test_txt_empty(self):
        """Empty text file should return empty string."""
        text = extract_text_from_file("empty.txt", b"")
        assert text == ""

    def test_pdf_dispatched(self):
        """.pdf files should be dispatched to extract_text_from_pdf."""
        with patch("src.knowledge.extract_text_from_pdf", return_value="PDF text") as mock_pdf:
            text = extract_text_from_file("doc.pdf", b"pdf-bytes")
        assert text == "PDF text"
        mock_pdf.assert_called_once_with(b"pdf-bytes")

    def test_docx_dispatched(self):
        """.docx files should be dispatched to extract_text_from_docx."""
        with patch("src.knowledge.extract_text_from_docx", return_value="DOCX text") as mock_docx:
            text = extract_text_from_file("report.docx", b"docx-bytes")
        assert text == "DOCX text"
        mock_docx.assert_called_once_with(b"docx-bytes")

    def test_unsupported_extension(self):
        """Unsupported extension should return empty string."""
        text = extract_text_from_file("image.png", b"png-bytes")
        assert text == ""

    def test_uppercase_extension(self):
        """Uppercase extension should be handled (.PDF, .DOCX)."""
        with patch("src.knowledge.extract_text_from_pdf", return_value="PDF text"):
            text = extract_text_from_file("DOC.PDF", b"pdf-bytes")
        assert text == "PDF text"

    def test_no_extension(self):
        """File with no extension should return empty string."""
        text = extract_text_from_file("README", b"some content")
        assert text == ""


# ============================================================
# SimpleKnowledgeBase add_file Tests
# ============================================================


class TestSimpleKnowledgeBaseAddFile:
    def test_add_txt_file(self):
        """add_file with .txt should extract and store."""
        kb = SimpleKnowledgeBase()
        doc_id = kb.add_file("hello.txt", "Hello World!".encode("utf-8"))
        assert doc_id is not None
        docs = kb.list_documents()
        assert len(docs) == 1
        assert docs[0].filename == "hello.txt"

    def test_add_pdf_file_mocked(self):
        """add_file with .pdf should extract via extract_text_from_file."""
        kb = SimpleKnowledgeBase()

        with patch("src.knowledge.extract_text_from_file", return_value="Extracted PDF text"):
            doc_id = kb.add_file("doc.pdf", b"fake-pdf")

        assert doc_id is not None
        docs = kb.list_documents()
        assert len(docs) == 1
        assert docs[0].filename == "doc.pdf"
        assert docs[0].char_count > 0

    def test_add_docx_file_mocked(self):
        """add_file with .docx should extract via extract_text_from_file."""
        kb = SimpleKnowledgeBase()

        with patch("src.knowledge.extract_text_from_file", return_value="Extracted DOCX text"):
            doc_id = kb.add_file("report.docx", b"fake-docx")

        assert doc_id is not None
        assert doc_id in kb._docs

    def test_add_empty_file_returns_none(self):
        """Empty file should return None."""
        kb = SimpleKnowledgeBase()
        doc_id = kb.add_file("empty.txt", b"")
        assert doc_id is None

    def test_add_unsupported_type(self):
        """Unsupported file type should return None."""
        kb = SimpleKnowledgeBase()
        doc_id = kb.add_file("image.png", b"data")
        assert doc_id is None

    def test_add_duplicate_file(self):
        """Duplicate file content should return existing doc_id."""
        kb = SimpleKnowledgeBase()
        doc_id1 = kb.add_file("test.txt", "Same content".encode("utf-8"))
        doc_id2 = kb.add_file("test.txt", "Same content".encode("utf-8"))
        assert doc_id1 == doc_id2
        assert len(kb.list_documents()) == 1  # No duplicates
