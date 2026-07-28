"""Tests for Auto Metadata Extraction (Feature 40)."""

import os
import tempfile
from pathlib import Path

import pytest
from src.core.metadata_extractor import extract_metadata, DocumentMetadata


class TestTextMetadata:
    """Test metadata extraction from text files."""

    def test_markdown_title_extracted(self):
        with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
            f.write("# My Document Title\n\nThis is content.")
            fpath = f.name

        try:
            meta = extract_metadata(fpath)
            assert "My Document Title" in meta.title
        finally:
            os.unlink(fpath)

    def test_author_extracted(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Author: John Doe\n\nContent here.")
            fpath = f.name

        try:
            meta = extract_metadata(fpath)
            assert "John Doe" in meta.author
        finally:
            os.unlink(fpath)

    def test_date_extracted(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Date: 2026-07-28\n\nContent.")
            fpath = f.name

        try:
            meta = extract_metadata(fpath)
            assert "2026-07-28" in meta.created_date
        finally:
            os.unlink(fpath)

    def test_file_extension_detected(self):
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
            f.write('{"key": "value"}')
            fpath = f.name

        try:
            meta = extract_metadata(fpath)
            assert meta.file_extension == "json"
        finally:
            os.unlink(fpath)

    def test_mime_type_guessed(self):
        meta = extract_metadata("test.pdf")
        assert meta.mime_type == "application/pdf"

    def test_nonexistent_file(self):
        meta = extract_metadata("/nonexistent/file.pdf")
        assert meta.filename == "file.pdf"
        assert meta.file_size_bytes == 0

    def test_basic_fields_present(self):
        meta = extract_metadata("dummy.txt")
        assert isinstance(meta, DocumentMetadata)
        assert hasattr(meta, "filename")
        assert hasattr(meta, "file_extension")
        assert hasattr(meta, "title")


class TestLanguageDetection:
    """Test language detection."""

    def test_vietnamese_detected(self):
        from src.core.metadata_extractor import _detect_language
        result = _detect_language("Xin chào, tôi là người Việt Nam. Hôm nay trời đẹp quá!")
        assert result == "vi"

    def test_english_detected(self):
        from src.core.metadata_extractor import _detect_language
        result = _detect_language("Hello, this is an English document. It has no Vietnamese characters.")
        assert result == "en"

    def test_short_text_unknown(self):
        from src.core.metadata_extractor import _detect_language
        result = _detect_language("Hi")
        assert result == "unknown"


class TestMimeType:
    def test_pdf_mime(self):
        from src.core.metadata_extractor import _guess_mime_type
        assert _guess_mime_type(".pdf") == "application/pdf"

    def test_unknown_mime(self):
        from src.core.metadata_extractor import _guess_mime_type
        assert _guess_mime_type(".xyz") == "application/octet-stream"
