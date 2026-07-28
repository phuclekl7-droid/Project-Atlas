"""Tests for OCRExtractor plugin (Feature 32)."""

import os
import tempfile
from pathlib import Path

import pytest
from src.plugins.ocr_extractor import OCRExtractorPlugin, _find_image_in_text


class TestFindImageInText:
    """Test image path extraction from text."""

    def test_image_marker_found(self):
        """[IMAGE:path] markers should be detected."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            img_path = f.name

        try:
            text = f"Please OCR this image: [IMAGE:{img_path}]"
            result = _find_image_in_text(text)
            assert result == img_path
        finally:
            os.unlink(img_path)

    def test_image_marker_not_found(self):
        """Absence of image should return None."""
        text = "Can you read this text? No image here."
        result = _find_image_in_text(text)
        assert result is None

    def test_file_path_detected(self):
        """Absolute file paths in text should be detected."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake png")
            img_path = f.name

        try:
            text = f"Extract text from {img_path}"
            result = _find_image_in_text(text)
            assert result == img_path
        finally:
            os.unlink(img_path)

    def test_nonexistent_file_ignored(self):
        """Files that don't exist should not be returned."""
        text = "Read /nonexistent/path/image.jpg"
        result = _find_image_in_text(text)
        assert result is None


class TestOCRExtractorPlugin:
    """Test OCRExtractor plugin behavior."""

    def test_plugin_name(self):
        plugin = OCRExtractorPlugin()
        assert plugin.name == "ocr_extractor"

    def test_plugin_description(self):
        plugin = OCRExtractorPlugin()
        assert "ocr" in plugin.description.lower() or "chữ" in plugin.description.lower()

    def test_empty_input(self):
        plugin = OCRExtractorPlugin()
        result = plugin.execute("")
        assert result.success is False
        assert result.output == ""

    def test_no_image_no_ocr_keyword(self):
        """Input without OCR keyword or image should return empty."""
        plugin = OCRExtractorPlugin()
        result = plugin.execute("Hello, how are you?")
        assert result.success is False
        assert result.output == ""

    def test_ocr_keyword_without_image(self):
        """OCR keyword without image should return error message."""
        plugin = OCRExtractorPlugin()
        result = plugin.execute("/ocr")
        assert result.success is False
        assert "không tìm thấy" in result.output.lower() or "not found" in result.output.lower()

    def test_ocr_keyword_with_nonexistent_image(self):
        """OCR keyword with bad path should return error."""
        plugin = OCRExtractorPlugin()
        result = plugin.execute("ocr /nonexistent/image.jpg")
        assert result.success is False
