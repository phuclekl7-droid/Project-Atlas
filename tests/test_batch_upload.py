"""
Tests for Feature #36: Batch Document Upload + Feature #38: Chunk Overlap Adjuster UI.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.knowledge.batch_upload import (
    ChunkConfig,
    BatchUploadResult,
    scan_directory,
    batch_upload,
    SUPPORTED_EXTENSIONS,
)


class TestChunkConfig:
    """Tests for the ChunkConfig dataclass."""

    def test_default_config(self):
        config = ChunkConfig()
        assert config.chunk_size == 500
        assert config.chunk_overlap == 100
        assert config.use_paragraph_boundaries

    def test_validate_min_chunk_size(self):
        with pytest.raises(ValueError, match="at least 50"):
            ChunkConfig(chunk_size=10).validate()

    def test_validate_max_chunk_size(self):
        with pytest.raises(ValueError, match="at most 5000"):
            ChunkConfig(chunk_size=10000).validate()

    def test_validate_negative_overlap(self):
        with pytest.raises(ValueError, match="non-negative"):
            ChunkConfig(chunk_overlap=-1).validate()

    def test_validate_overlap_gte_size(self):
        with pytest.raises(ValueError, match="less than"):
            ChunkConfig(chunk_size=100, chunk_overlap=100).validate()

    def test_validate_valid(self):
        config = ChunkConfig(chunk_size=300, chunk_overlap=50)
        config.validate()  # Should not raise

    def test_to_dict(self):
        config = ChunkConfig(chunk_size=200, chunk_overlap=30)
        d = config.to_dict()
        assert d["chunk_size"] == 200
        assert d["chunk_overlap"] == 30

    def test_from_dict(self):
        config = ChunkConfig.from_dict({"chunk_size": "300", "chunk_overlap": "50"})
        assert config.chunk_size == 300
        assert config.chunk_overlap == 50


class TestScanDirectory:
    """Tests for directory scanning."""

    def test_directory_not_found(self):
        with pytest.raises(FileNotFoundError):
            scan_directory("/nonexistent/path")

    def test_empty_directory(self, tmp_path):
        files = scan_directory(str(tmp_path))
        assert len(files) == 0

    def test_find_txt_files(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello")
        (tmp_path / "notes.md").write_text("# Notes")
        files = scan_directory(str(tmp_path), extensions={".txt"})
        assert len(files) == 1
        assert files[0].suffix == ".txt"

    def test_recursive_scan(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "root.txt").write_text("root")
        (subdir / "nested.txt").write_text("nested")
        files = scan_directory(str(tmp_path), recursive=True)
        assert len(files) == 2

    def test_non_recursive_scan(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "root.txt").write_text("root")
        (subdir / "nested.txt").write_text("nested")
        files = scan_directory(str(tmp_path), recursive=False)
        assert len(files) == 1

    def test_max_files_limit(self, tmp_path):
        for i in range(10):
            (tmp_path / f"file_{i}.txt").write_text(str(i))
        files = scan_directory(str(tmp_path), max_files=3)
        assert len(files) <= 3


class TestBatchUploadResult:
    """Tests for BatchUploadResult."""

    def test_summary_success(self):
        result = BatchUploadResult(total_files=5, successful=5)
        assert "successfully" in result.summary
        assert "5" in result.summary

    def test_summary_with_errors(self):
        result = BatchUploadResult(total_files=3, successful=2, failed=1, errors=["File corrupt"])
        assert "errors" in result.summary.lower()


class TestBatchUpload:
    """Tests for batch_upload function."""

    def test_batch_upload_success(self, tmp_path):
        # Create test files
        (tmp_path / "doc1.txt").write_text("Content 1")
        (tmp_path / "doc2.txt").write_text("Content 2")

        mock_kb = MagicMock()
        mock_kb.add_file.return_value = "doc_id_123"

        result = batch_upload(mock_kb, str(tmp_path))
        assert result.successful == 2
        assert mock_kb.add_file.call_count == 2

    def test_batch_upload_with_errors(self, tmp_path):
        (tmp_path / "good.txt").write_text("Good")
        (tmp_path / "bad.txt").write_text("Bad content")

        mock_kb = MagicMock()
        def mock_add(*args, **kwargs):
            if "bad" in args[0]:
                raise ValueError("Corrupt file")
            return "doc_id"

        mock_kb.add_file.side_effect = mock_add

        result = batch_upload(mock_kb, str(tmp_path))
        assert result.failed == 1
        assert result.successful == 1

    def test_directory_not_found(self):
        mock_kb = MagicMock()
        result = batch_upload(mock_kb, "/nonexistent/path")
        assert result.total_files == 0
        assert len(result.errors) > 0
