"""
OCR Image Text Extraction Plugin (Feature 32)

Extracts text from images using OCR libraries. Supports multiple backends:
  - pytesseract (primary, if installed)
  - easyocr (fallback, if installed)
  - Pillow + built-in simple threshold (basic fallback)

Usage:
    plugin = OCRExtractorPlugin()
    result = plugin.execute("/ocr path/to/image.jpg")
    result = plugin.execute("extract text from this image")
    result = plugin.execute("Can you read this receipt?")  # auto-detect image path
"""

import base64
import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from src.plugin import BasePlugin, PluginResult

# Try optional dependencies
_HAS_PILLOW = False
_HAS_TESSERACT = False
_HAS_EASYOCR = False

try:
    from PIL import Image
    _HAS_PILLOW = True
except ImportError:
    Image = None  # type: ignore

try:
    import pytesseract
    _HAS_TESSERACT = True
except ImportError:
    pytesseract = None  # type: ignore

try:
    import easyocr
    _HAS_EASYOCR = True
except ImportError:
    easyocr = None  # type: ignore


def _preprocess_image(image_path: str) -> Optional[bytes]:
    """Load and preprocess an image for OCR.

    Converts to grayscale, enhances contrast, and returns PNG bytes.

    Args:
        image_path: Path to the image file

    Returns:
        PNG bytes of preprocessed image, or None if loading fails
    """
    if not _HAS_PILLOW:
        return None

    try:
        img = Image.open(image_path)
        # Convert to grayscale
        if img.mode != "L":
            img = img.convert("L")
        # Enhance contrast (simple auto-level)
        img = img.point(lambda x: 0 if x < 40 else 255 if x > 220 else x)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _find_image_in_text(text: str) -> Optional[str]:
    """Extract an image file path from text.

    Looks for:
      - /path/to/file.jpg or \path\to\file.png
      - [IMAGE:path] markers
      - base64 data URIs (data:image/...)

    Args:
        text: User input that may contain image references

    Returns:
        Extracted image path, or None
    """
    # Check for [IMAGE:path] markers first
    img_marker = re.search(r"\[IMAGE:\s*([^\]]+)\]", text)
    if img_marker:
        path = img_marker.group(1).strip()
        if os.path.isfile(path):
            return path

    # Check for file paths with image extensions
    img_extensions = r"\.(?:jpg|jpeg|png|gif|bmp|tiff|tif|webp)"
    path_match = re.search(
        rf"[\"']?([^\s\"']+{img_extensions})[\"']?", text, re.IGNORECASE
    )
    if path_match:
        path = path_match.group(1).strip().strip("\"'")
        if os.path.isfile(path):
            return path

    # Check for base64 data URIs
    if "data:image/" in text:
        b64_match = re.search(
            r"data:image/(?:png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]+)",
            text,
        )
        if b64_match:
            # Decode and save to temp file
            try:
                img_data = base64.b64decode(b64_match.group(1))
                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ) as f:
                    f.write(img_data)
                    return f.name
            except Exception:
                pass

    return None


def _extract_with_tesseract(image_path: str) -> Optional[str]:
    """Extract text using Tesseract OCR.

    Args:
        image_path: Path to the image

    Returns:
        Extracted text, or None if failed
    """
    if not _HAS_TESSERACT or not _HAS_PILLOW:
        return None

    try:
        # Preprocess image for better OCR
        preprocessed = _preprocess_image(image_path)
        if preprocessed:
            img = Image.open(BytesIO(preprocessed))
        else:
            img = Image.open(image_path)

        # Try different PSM modes
        configs = [
            "--psm 3 --oem 3",   # Default: fully automatic
            "--psm 6 --oem 3",   # Assume uniform block of text
            "--psm 4 --oem 3",   # Assume single column
        ]

        for config in configs:
            try:
                text = pytesseract.image_to_string(img, config=config, lang="vie+eng")
                if text and text.strip() and len(text.strip()) > 3:
                    return text.strip()
            except Exception:
                continue

        return None
    except Exception:
        return None


def _extract_with_easyocr(image_path: str) -> Optional[str]:
    """Extract text using EasyOCR with Vietnamese support.

    Args:
        image_path: Path to the image

    Returns:
        Extracted text, or None if failed
    """
    if not _HAS_EASYOCR:
        return None

    try:
        reader = easyocr.Reader(["vi", "en"], gpu=False)
        results = reader.readtext(image_path, detail=0)
        if results:
            return "\n".join(results)
        return None
    except Exception:
        return None


def _available_backends() -> list[str]:
    """Get list of available OCR backends."""
    backends = []
    if _HAS_TESSERACT:
        backends.append("tesseract")
    if _HAS_EASYOCR:
        backends.append("easyocr")
    if _HAS_PILLOW:
        backends.append("pillow (image processing only)")
    return backends


class OCRExtractorPlugin(BasePlugin):
    """Plugin that extracts text from images using OCR."""

    @property
    def name(self) -> str:
        return "ocr_extractor"

    @property
    def description(self) -> str:
        backends = _available_backends()
        if backends:
            return f"Đọc chữ từ ảnh chụp/scan tài liệu (backends: {', '.join(backends[:2])})"
        return "Đọc chữ từ ảnh chụp/scan tài liệu (cần cài pytesseract hoặc easyocr)"

    def execute(self, user_input: str) -> PluginResult:
        """Extract text from an image referenced in the user input.

        Args:
            user_input: Text containing an image path or [IMAGE:path] marker

        Returns:
            PluginResult with extracted text
        """
        if not user_input or not user_input.strip():
            return PluginResult(success=False, output="", plugin_name=self.name)

        # Check if this looks like an OCR request
        ocr_keywords = [
            "ocr", "đọc chữ", "extract text", "read text",
            "recognize", "nhận diện", "scan",
            "/ocr",
        ]
        is_ocr_request = any(kw in user_input.lower() for kw in ocr_keywords)

        if not is_ocr_request:
            # Only activate if an image path is explicitly provided
            image_path = _find_image_in_text(user_input)
            if image_path is None:
                return PluginResult(success=False, output="", plugin_name=self.name)
        else:
            image_path = _find_image_in_text(user_input)

            if image_path is None:
                return PluginResult(
                    success=False,
                    output=(
                        "Không tìm thấy file ảnh trong câu hỏi. "
                        "Hãy upload ảnh lên trước, sau đó gõ `/ocr` hoặc "
                        "'đọc chữ từ ảnh này'."
                    ),
                    plugin_name=self.name,
                )

        # Verify file exists and is an image
        if not os.path.isfile(image_path):
            return PluginResult(
                success=False,
                output=f"File không tồn tại: {image_path}",
                plugin_name=self.name,
            )

        # Check available backends
        if not _HAS_TESSERACT and not _HAS_EASYOCR:
            return PluginResult(
                success=False,
                output=(
                    "⚠️ **Chưa cài OCR engine**\n\n"
                    "Vui lòng cài một trong các gói sau:\n"
                    "- `pip install pytesseract` (cần cài Tesseract: "
                    "https://github.com/tesseract-ocr/tesseract)\n"
                    "- `pip install easyocr`"
                ),
                plugin_name=self.name,
            )

        # Try backends in priority order
        text = None
        backend_used = None

        if _HAS_TESSERACT:
            text = _extract_with_tesseract(image_path)
            backend_used = "Tesseract OCR"

        if text is None and _HAS_EASYOCR:
            text = _extract_with_easyocr(image_path)
            backend_used = "EasyOCR"

        if text is None or not text.strip():
            return PluginResult(
                success=False,
                output=(
                    f"🔍 **Không tìm thấy văn bản** trong ảnh "
                    f"(backend: {backend_used or 'N/A'}).\n\n"
                    f"Thử:\n"
                    f"- Ảnh có độ phân giải cao hơn\n"
                    f"- Ảnh chụp thẳng, không nghiêng\n"
                    f"- Văn bản in rõ ràng"
                ),
                plugin_name=self.name,
            )

        # Format output
        filename = Path(image_path).name
        word_count = len(text.split())
        char_count = len(text)

        output_lines = [
            f"📝 **Văn bản từ {filename}**",
            f"> Số từ: {word_count} | Số ký tự: {char_count} | Backend: {backend_used}",
            "",
            text,
        ]

        return PluginResult(
            success=True,
            output="\n".join(output_lines),
            plugin_name=self.name,
            data={
                "filename": filename,
                "word_count": word_count,
                "char_count": char_count,
                "backend": backend_used,
                "text": text[:1000],  # Preview
            },
        )
