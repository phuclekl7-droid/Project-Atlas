"""
Tests for Feature #37: Document Versioning.
"""

import tempfile
from pathlib import Path

import pytest

from src.core.document_versions import DocumentVersionTracker, DocumentVersion


class TestDocumentVersionTracker:
    def test_add_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            version = tracker.add_version("doc_1", "report.pdf", "Q1 revenue increased by 20%")
            assert version is not None
            assert version.version == 1
            assert version.filename == "report.pdf"

    def test_multiple_versions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            tracker.add_version("doc_1", "r.pdf", "version 1 content")
            v2 = tracker.add_version("doc_1", "r.pdf", "version 2 updated content")
            assert v2.version == 2

    def test_duplicate_content_skips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            v1 = tracker.add_version("doc_1", "r.pdf", "same content")
            v2 = tracker.add_version("doc_1", "r.pdf", "same content")
            assert v2.version == v1.version  # Same version returned

    def test_list_versions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            tracker.add_version("doc_1", "r.pdf", "v1")
            tracker.add_version("doc_1", "r.pdf", "v2")
            versions = tracker.list_versions("doc_1")
            assert len(versions) == 2
            assert versions[0].version == 2  # Newest first

    def test_list_versions_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            versions = tracker.list_versions("nonexistent")
            assert versions == []

    def test_get_version_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            tracker.add_version("doc_1", "r.pdf", "original content")
            content = tracker.get_version_content("doc_1", 1)
            assert content == "original content"

    def test_get_version_content_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            content = tracker.get_version_content("nonexistent", 1)
            assert content is None

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            tracker.add_version("doc_1", "r.pdf", "version 1")
            tracker.add_version("doc_1", "r.pdf", "version 2 updated")
            rolled_back = tracker.rollback("doc_1", 1)
            assert rolled_back == "version 1"
            versions = tracker.list_versions("doc_1")
            assert len(versions) == 3  # 2 originals + 1 rollback

    def test_delete_doc_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            tracker.add_version("doc_1", "r.pdf", "content")
            deleted = tracker.delete_doc_history("doc_1")
            assert deleted == 1
            assert tracker.list_versions("doc_1") == []

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            tracker.add_version("doc_1", "r.pdf", "content")
            tracker.add_version("doc_2", "r2.pdf", "more content")
            stats = tracker.get_stats()
            assert stats["document_count"] == 2
            assert stats["total_versions"] == 2

    def test_empty_content_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = DocumentVersionTracker(path=tmpdir)
            version = tracker.add_version("doc_1", "r.pdf", "")
            assert version is None

    def test_version_formatted_time(self):
        v = DocumentVersion(version=1, doc_id="d1", filename="f.pdf", content_hash="abc", char_count=10, timestamp=1000000)
        assert v.formatted_time is not None
