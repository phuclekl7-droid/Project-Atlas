"""
Image utilities: save/load/encode images for vision model support.

Stores images in a dedicated directory under the project data folder.
Supports JPEG, PNG, WebP, GIF (static), and BMP formats.
Provides base64 encoding for API calls to vision models (OpenAI, Ollama).
"""
import base64
import io
import os
import uuid
from pathlib import Path
from typing import Optional

from src.core import setup_logger

logger = setup_logger("image_utils")

# Supported image extensions for upload and processing
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

# Max image file size (10 MB)
MAX_IMAGE_SIZE = 10 * 1024 * 1024


def is_supported_image(filename: str) -> bool:
    """Check if a filename has a supported image extension."""
    ext = Path(filename).suffix.lower()
    return ext in SUPPORTED_IMAGE_EXTENSIONS


def get_mime_type(filename: str) -> str:
    """Get MIME type from filename extension."""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/png")


class ImageStore:
    """
    Saves uploaded images to disk and provides methods to encode them
    for vision model API calls.

    Images are stored as: <store_path>/<uuid>.<ext>
    A mapping of message_id -> image_path is maintained in a JSON sidecar file.
    """

    def __init__(self, store_path: str = "data/images"):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"ImageStore initialized: {self.store_path}")

    def save_image(self, filename: str, data: bytes) -> Optional[str]:
        """
        Save an uploaded image to disk.

        Args:
            filename: Original filename (used to determine extension)
            data: Raw image bytes

        Returns:
            Relative path to saved image, or None if save failed
        """
        if not data:
            logger.warning("Cannot save empty image data")
            return None

        if len(data) > MAX_IMAGE_SIZE:
            logger.warning(f"Image too large: {len(data)} bytes (max {MAX_IMAGE_SIZE})")
            return None

        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            logger.warning(f"Unsupported image type: {ext}")
            return None

        # Generate unique filename
        image_id = str(uuid.uuid4())[:12]
        saved_name = f"{image_id}{ext}"
        file_path = self.store_path / saved_name

        try:
            file_path.write_bytes(data)
            logger.debug(f"Saved image: {file_path} ({len(data)} bytes)")
            return str(file_path)
        except OSError as e:
            logger.error(f"Failed to save image {file_path}: {e}")
            return None

    def load_image(self, file_path: str) -> Optional[bytes]:
        """
        Load image bytes from a saved path.

        Args:
            file_path: Relative or absolute path to saved image

        Returns:
            Raw image bytes, or None if not found
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.store_path / path.name

        if not path.exists():
            logger.warning(f"Image not found: {path}")
            return None

        try:
            return path.read_bytes()
        except OSError as e:
            logger.error(f"Failed to load image {path}: {e}")
            return None

    def encode_image(self, file_path: str) -> Optional[str]:
        """
        Load an image and encode it as a base64 data URI string.

        Returns format: "data:image/jpeg;base64,/9j/4AAQ..."
        Suitable for OpenAI vision API and Ollama vision models.

        Args:
            file_path: Path to the saved image

        Returns:
            Base64 data URI string, or None if encoding failed
        """
        data = self.load_image(file_path)
        if data is None:
            return None

        mime = get_mime_type(file_path)
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    def encode_image_raw(self, file_path: str) -> Optional[tuple[str, str]]:
        """
        Encode image for Gemini API (which needs raw base64 + mime separately).

        Returns:
            Tuple of (base64_string, mime_type), or None if failed
        """
        data = self.load_image(file_path)
        if data is None:
            return None

        mime = get_mime_type(file_path)
        b64 = base64.b64encode(data).decode("utf-8")
        return (b64, mime)

    def delete_image(self, file_path: str) -> bool:
        """Delete a saved image file."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.store_path / path.name

        try:
            if path.exists():
                path.unlink()
                logger.debug(f"Deleted image: {path}")
                return True
            return False
        except OSError as e:
            logger.error(f"Failed to delete image {path}: {e}")
            return False

    def get_image_url(self, file_path: str) -> str:
        """
        Get a local file URL for displaying in Streamlit.

        Returns a path that Streamlit's st.image() can use.
        """
        path = Path(file_path)
        if path.exists():
            return str(path.absolute())
        return str((self.store_path / path.name).absolute())

    def cleanup_orphaned(self, keep_paths: set[str]) -> int:
        """
        Delete image files that are not in the keep_paths set.

        Args:
            keep_paths: Set of file paths to keep

        Returns:
            Number of deleted files
        """
        count = 0
        for f in self.store_path.iterdir():
            f_str = str(f)
            if f.is_file() and f_str not in keep_paths:
                try:
                    f.unlink()
                    count += 1
                except OSError:
                    pass
        if count:
            logger.debug(f"Cleaned up {count} orphaned images")
        return count

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        total_files = 0
        total_size = 0
        for f in self.store_path.iterdir():
            if f.is_file():
                total_files += 1
                total_size += f.stat().st_size
        return {
            "total_images": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "store_path": str(self.store_path),
        }
