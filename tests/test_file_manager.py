"""
Unit tests for File System Manager Plugin.

Tests:
- Path traversal prevention (_resolve_safe_path)
- Text file detection (_is_text_file)
- File size formatting (_format_size)
- Plugin metadata
- Command parsing (/read, /write, /list, /info, /mkdir)
- File operations (mocked filesystem)
- Error handling (path traversal, not found, binary file)
"""

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.file_manager import (
    FileManagerPlugin,
    _resolve_safe_path,
    _is_text_file,
    _format_size,
    _DEFAULT_ALLOWED_DIR,
)


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestFileManagerMetadata:
    def test_plugin_name(self):
        plugin = FileManagerPlugin(allowed_dir=tempfile.gettempdir())
        assert plugin.name == "file_manager"

    def test_plugin_description(self):
        plugin = FileManagerPlugin(allowed_dir=tempfile.gettempdir())
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_is_baseplugin_subclass(self):
        assert issubclass(FileManagerPlugin, BasePlugin)

    def test_default_allowed_dir(self):
        plugin = FileManagerPlugin()
        assert plugin.allowed_dir is not None
        assert Path(plugin.allowed_dir).exists()


# ============================================================
# Path Traversal Prevention Tests
# ============================================================


class TestResolveSafePath:
    def test_basic_relative_path(self, tmp_path):
        """Relative path within allowed dir should resolve."""
        result = _resolve_safe_path("test.txt", str(tmp_path))
        assert result is not None
        assert result == (tmp_path / "test.txt").resolve()

    def test_absolute_path_within_allowed(self, tmp_path):
        """Absolute path within allowed dir should resolve."""
        filepath = tmp_path / "subdir" / "test.txt"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        result = _resolve_safe_path(str(filepath), str(tmp_path))
        assert result is not None
        assert result == filepath.resolve()

    def test_path_traversal_outside(self, tmp_path):
        """Path with '../' escaping allowed dir should return None."""
        result = _resolve_safe_path("../outside.txt", str(tmp_path))
        assert result is None

    def test_absolute_outside_allowed(self, tmp_path):
        """Absolute path outside allowed dir should return None."""
        result = _resolve_safe_path(str(Path.home() / "secret.txt"), str(tmp_path))
        assert result is None

    def test_subdirectory_within_allowed(self, tmp_path):
        """Subdirectory path should work."""
        (tmp_path / "sub").mkdir(exist_ok=True)
        result = _resolve_safe_path("sub/file.txt", str(tmp_path))
        assert result is not None
        assert result == (tmp_path / "sub" / "file.txt").resolve()

    def test_empty_path(self, tmp_path):
        """Empty path should resolve to allowed dir itself."""
        result = _resolve_safe_path("", str(tmp_path))
        assert result == tmp_path.resolve()

    def test_current_dir(self, tmp_path):
        """'.' should resolve to allowed dir."""
        result = _resolve_safe_path(".", str(tmp_path))
        assert result == tmp_path.resolve()


# ============================================================
# Text File Detection Tests
# ============================================================


class TestIsTextFile:
    def test_text_file_returns_true(self, tmp_path):
        """UTF-8 text file should be detected as text."""
        filepath = tmp_path / "test.txt"
        filepath.write_text("Hello, world!\nThis is a text file.", encoding="utf-8")
        assert _is_text_file(filepath) is True

    def test_binary_file_returns_false(self, tmp_path):
        """File with null bytes should be detected as binary."""
        filepath = tmp_path / "test.bin"
        filepath.write_bytes(b"\x00\x01\x02\x03\x00\x00\x00\x01")
        assert _is_text_file(filepath) is False

    def test_markdown_file(self, tmp_path):
        """Markdown file should be text."""
        filepath = tmp_path / "readme.md"
        filepath.write_text("# Title\n\nContent here.", encoding="utf-8")
        assert _is_text_file(filepath) is True

    def test_python_file(self, tmp_path):
        """Python file should be text."""
        filepath = tmp_path / "script.py"
        filepath.write_text("print('hello')", encoding="utf-8")
        assert _is_text_file(filepath) is True

    def test_not_exists_returns_false(self, tmp_path):
        """Non-existent file should return False."""
        filepath = tmp_path / "nonexistent.txt"
        assert _is_text_file(filepath) is False


# ============================================================
# Size Formatting Tests
# ============================================================


class TestFormatSize:
    def test_bytes(self):
        assert "B" in _format_size(500)

    def test_kilobytes(self):
        result = _format_size(1500)
        assert "KB" in result

    def test_megabytes(self):
        result = _format_size(2_500_000)
        assert "MB" in result

    def test_gigabytes(self):
        result = _format_size(2_500_000_000)
        assert "GB" in result

    def test_zero(self):
        result = _format_size(0)
        assert "0" in result or "B" in result


# ============================================================
# Command Parsing Tests
# ============================================================


class TestCommandParsing:
    def test_no_command_prefix(self, tmp_path):
        """Input without /read, /write, etc. should return success=False with empty output."""
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("hello world")
        assert result.success is False
        assert result.output == ""

    def test_empty_input(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("")
        assert result.success is False
        assert result.output == ""


# ============================================================
# File Operations Tests
# ============================================================


class TestFileRead:
    def test_read_existing_file(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        filepath = tmp_path / "test.txt"
        filepath.write_text("Hello, world!", encoding="utf-8")

        result = plugin.execute(f"/read test.txt")
        assert result.success is True
        assert "Hello" in result.output

    def test_read_nonexistent_file(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/read nonexistent.txt")
        assert result.success is False
        assert "tồn tại" in result.output

    def test_read_outside_allowed_dir(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/read ../secret.txt")
        assert result.success is False

    def test_read_directory_instead_of_file(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute(f"/read .")
        assert result.success is False


class TestFileWrite:
    def test_write_new_file(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/write test.txt Hello, world!")
        assert result.success is True
        assert (tmp_path / "test.txt").exists()
        assert (tmp_path / "test.txt").read_text(encoding="utf-8") == "Hello, world!"

    def test_write_no_content(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/write test.txt")
        assert result.success is False

    def test_write_outside_allowed_dir(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/write ../secret.txt content")
        assert result.success is False


class TestFileList:
    def test_list_directory(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")

        result = plugin.execute("/list .")
        assert result.success is True
        assert "a.txt" in result.output
        assert "b.txt" in result.output

    def test_list_nonexistent_path(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/list nonexistent")
        assert result.success is False

    def test_list_empty_directory(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/list .")
        assert result.success is True


class TestFileInfo:
    def test_info_existing_file(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        (tmp_path / "test.txt").write_text("content", encoding="utf-8")

        result = plugin.execute("/info test.txt")
        assert result.success is True
        assert "test.txt" in result.output

    def test_info_nonexistent_file(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/info nonexistent.txt")
        assert result.success is False

    def test_info_outside_allowed_dir(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/info ../secret.txt")
        assert result.success is False


class TestFileMkdir:
    def test_mkdir_new(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/mkdir newdir")
        assert result.success is True
        assert (tmp_path / "newdir").is_dir()

    def test_mkdir_existing(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        (tmp_path / "existing").mkdir()
        result = plugin.execute("/mkdir existing")
        assert result.success is False

    def test_mkdir_outside_allowed(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/mkdir ../outsider")
        assert result.success is False


# ============================================================
# Data Structure Tests
# ============================================================


class TestFileManagerData:
    def test_read_data_has_path_and_size(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        filepath = tmp_path / "test.txt"
        filepath.write_text("Hello!", encoding="utf-8")

        result = plugin.execute("/read test.txt")
        assert result.data is not None
        assert "path" in result.data
        assert "size" in result.data

    def test_write_data_has_path_and_size(self, tmp_path):
        plugin = FileManagerPlugin(allowed_dir=str(tmp_path))
        result = plugin.execute("/write test.txt Hello!")
        assert result.data is not None
        assert "path" in result.data
        assert "size" in result.data
