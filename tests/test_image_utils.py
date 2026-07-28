"""
Tests for ImageStore utility and Message image handling.
"""

import os

import pytest

from src.core.image_utils import ImageStore, is_supported_image, get_mime_type
from src.memory import Message


# ============================================================
# ImageStore Tests
# ============================================================

class TestImageStoreInit:
    def test_init_creates_directory(self, tmp_path):
        store_path = tmp_path / "test_images"
        store = ImageStore(str(store_path))
        assert store_path.exists()
        assert store_path.is_dir()
        store = None  # cleanup

    def test_init_existing_directory(self, tmp_path):
        d = tmp_path / "images"
        d.mkdir()
        store = ImageStore(str(d))
        assert d.exists()


class TestImageStoreSave:
    def test_save_png(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"fake_png_data"
        path = store.save_image("test.png", data)
        assert path is not None
        assert os.path.exists(path)

    def test_save_jpg(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"fake_jpg_data"
        path = store.save_image("photo.jpg", data)
        assert path is not None
        assert path.endswith(".jpg")

    def test_save_unsupported_format(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"data"
        path = store.save_image("file.txt", data)
        assert path is None

    def test_save_empty_data(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        path = store.save_image("test.png", b"")
        assert path is None

    def test_save_oversized(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"x" * (10 * 1024 * 1024 + 1)  # > 10MB
        path = store.save_image("big.png", data)
        assert path is None


class TestImageStoreLoad:
    def test_load_existing(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"hello_image"
        saved = store.save_image("test.png", data)
        loaded = store.load_image(saved)
        assert loaded == data

    def test_load_nonexistent(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        loaded = store.load_image("nonexistent.png")
        assert loaded is None


class TestImageStoreEncode:
    def test_encode_png(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"png_data"
        saved = store.save_image("test.png", data)
        encoded = store.encode_image(saved)
        assert encoded is not None
        assert encoded.startswith("data:image/png;base64,")

    def test_encode_jpg(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"jpg_data"
        saved = store.save_image("photo.jpg", data)
        encoded = store.encode_image(saved)
        assert encoded.startswith("data:image/jpeg;base64,")

    def test_encode_nonexistent(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        encoded = store.encode_image("nonexistent.png")
        assert encoded is None


class TestImageStoreEncodeRaw:
    def test_encode_raw(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"test_data"
        saved = store.save_image("test.png", data)
        result = store.encode_image_raw(saved)
        assert result is not None
        b64_str, mime = result
        assert mime == "image/png"
        assert isinstance(b64_str, str)


class TestImageStoreDelete:
    def test_delete_existing(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        data = b"delete_me"
        saved = store.save_image("del.png", data)
        assert store.delete_image(saved) is True
        assert not os.path.exists(saved)

    def test_delete_nonexistent(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        assert store.delete_image("nonexistent.png") is False


class TestImageStoreGetStats:
    def test_empty_stats(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        stats = store.get_storage_stats()
        assert stats["total_images"] == 0

    def test_nonempty_stats(self, tmp_path):
        store = ImageStore(str(tmp_path / "img"))
        store.save_image("a.png", b"aaa")
        store.save_image("b.png", b"bbbb")
        stats = store.get_storage_stats()
        assert stats["total_images"] == 2
        assert stats["total_size_bytes"] > 0


# ============================================================
# Utility functions
# ============================================================

class TestIsSupportedImage:
    def test_supported(self):
        assert is_supported_image("photo.jpg") is True
        assert is_supported_image("photo.jpeg") is True
        assert is_supported_image("image.png") is True
        assert is_supported_image("anim.webp") is True
        assert is_supported_image("img.gif") is True
        assert is_supported_image("img.bmp") is True
        assert is_supported_image("IMG.JPG") is True

    def test_unsupported(self):
        assert is_supported_image("file.txt") is False
        assert is_supported_image("doc.pdf") is False
        assert is_supported_image("") is False


class TestGetMimeType:
    def test_mime_map(self):
        assert get_mime_type("photo.jpg") == "image/jpeg"
        assert get_mime_type("photo.jpeg") == "image/jpeg"
        assert get_mime_type("img.png") == "image/png"
        assert get_mime_type("anim.webp") == "image/webp"
        assert get_mime_type("img.gif") == "image/gif"
        assert get_mime_type("img.bmp") == "image/bmp"

    def test_unknown(self):
        assert get_mime_type("file.txt") == "image/png"


# ============================================================
# Message Image Handling Tests
# ============================================================

class TestMessageImageContent:
    def test_make_image_content(self):
        content = Message.make_image_content("/tmp/test.png", "Describe this")
        assert content == "[IMAGE:/tmp/test.png]Describe this"

    def test_make_image_content_no_text(self):
        content = Message.make_image_content("/tmp/test.png")
        assert content == "[IMAGE:/tmp/test.png]"

    def test_image_path_extraction(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="[IMAGE:/data/abc.png]What is this?",
                       created_at="2026-01-01T00:00:00Z")
        assert msg.image_path == "/data/abc.png"
        assert msg.has_image() is True

    def test_image_path_no_image(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="Just text",
                       created_at="2026-01-01T00:00:00Z")
        assert msg.image_path is None
        assert msg.has_image() is False

    def test_text_content_with_image(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="[IMAGE:/img.png]Describe this image",
                       created_at="2026-01-01T00:00:00Z")
        assert msg.text_content == "Describe this image"

    def test_text_content_without_image(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="Just text",
                       created_at="2026-01-01T00:00:00Z")
        assert msg.text_content == "Just text"

    def test_text_content_image_only(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="[IMAGE:/img.png]",
                       created_at="2026-01-01T00:00:00Z")
        assert msg.text_content == ""

    def test_to_dict_includes_image_path(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="[IMAGE:/img.png]Describe",
                       created_at="2026-01-01T00:00:00Z")
        d = msg.to_dict()
        assert d.get("image_path") == "/img.png"

    def test_to_dict_no_image(self):
        msg = Message(id=1, session_id="abc", role="user",
                       content="Hello",
                       created_at="2026-01-01T00:00:00Z")
        d = msg.to_dict()
        assert "image_path" not in d

    def test_to_context_dict_strips_image_ref(self):
        """to_context_dict should return text_content without image prefix."""
        msg = Message(id=1, session_id="abc", role="user",
                       content="[IMAGE:/img.png]Describe this image",
                       created_at="2026-01-01T00:00:00Z")
        ctx = msg.to_context_dict()
        assert ctx["content"] == "Describe this image"
        assert "[IMAGE:" not in ctx["content"]
