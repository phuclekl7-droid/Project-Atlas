"""
Document Versioning (Feature #37).
Tracks versions of documents in the Knowledge Base.

Provides:
- Version history for each document
- Snapshot on each add/update
- Rollback to previous version
- Version diff summary

Usage:
    tracker = DocumentVersionTracker(path="data/versions")
    tracker.add_version(doc_id="abc", filename="report.pdf", content="Q1 results...")
    versions = tracker.list_versions(doc_id="abc")
    tracker.rollback(doc_id="abc", version=1)
"""

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core import setup_logger

logger = setup_logger("doc_versions")


@dataclass
class DocumentVersion:
    """A single version of a document."""
    version: int = 0
    doc_id: str = ""
    filename: str = ""
    content_hash: str = ""
    char_count: int = 0
    timestamp: float = 0.0
    change_summary: str = ""

    @property
    def formatted_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")


class DocumentVersionTracker:
    """
    Tracks document versions for the Knowledge Base.

    Each time a document with the same doc_id is added,
    a new version is recorded with a snapshot.

    Usage:
        tracker = DocumentVersionTracker()
        v1 = tracker.add_version("doc_1", "report.pdf", "Q1 revenue increased")
        v2 = tracker.add_version("doc_1", "report.pdf", "Q1 revenue increased by 20%")
        history = tracker.list_versions("doc_1")  # [v2, v1]
        tracker.rollback("doc_1", 1)  # Rollback to v1 content
    """

    def __init__(self, path: str = "data/versions"):
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # In-memory index: doc_id -> list of DocumentVersion
        self._versions: dict[str, list[DocumentVersion]] = {}

        self._load_index()

    def _index_path(self) -> Path:
        return self._path / "_index.json"

    def _versions_dir(self) -> Path:
        return self._path / "snapshots"

    def _load_index(self):
        """Load the version index from disk."""
        index_file = self._index_path()
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                for doc_id, versions_data in data.items():
                    self._versions[doc_id] = [
                        DocumentVersion(**v) for v in versions_data
                    ]
                logger.debug(f"Loaded version index: {len(self._versions)} documents")
            except Exception as e:
                logger.warning(f"Failed to load version index: {e}")

    def _save_index(self):
        """Save the version index to disk."""
        index_file = self._index_path()
        try:
            data = {}
            for doc_id, versions in self._versions.items():
                data[doc_id] = [{
                    "version": v.version,
                    "doc_id": v.doc_id,
                    "filename": v.filename,
                    "content_hash": v.content_hash,
                    "char_count": v.char_count,
                    "timestamp": v.timestamp,
                    "change_summary": v.change_summary,
                } for v in versions]
            index_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save version index: {e}")

    def add_version(
        self,
        doc_id: str,
        filename: str,
        content: str,
        change_summary: str = "",
    ) -> Optional[DocumentVersion]:
        """
        Add a new version of a document.

        Args:
            doc_id: Document ID
            filename: Source filename
            content: Full document text content
            change_summary: Description of changes in this version

        Returns:
            The DocumentVersion if successful
        """
        if not content.strip():
            logger.warning(f"Empty content for {filename}, skipping version")
            return None

        content_hash = hashlib.md5(content.encode()).hexdigest()
        char_count = len(content)

        with self._lock:
            versions = self._versions.get(doc_id, [])
            new_version_num = len(versions) + 1

            # Check for duplicate content (skip if identical to latest)
            if versions:
                latest = versions[-1]
                if latest.content_hash == content_hash:
                    logger.debug(f"No changes for {filename} (v{latest.version}), skipping")
                    return latest

            version = DocumentVersion(
                version=new_version_num,
                doc_id=doc_id,
                filename=filename,
                content_hash=content_hash,
                char_count=char_count,
                timestamp=time.time(),
                change_summary=change_summary or f"Version {new_version_num}",
            )

            # Save snapshot to disk
            self._versions_dir().mkdir(parents=True, exist_ok=True)
            snapshot_file = self._versions_dir() / f"{doc_id}_v{new_version_num}.txt"
            try:
                snapshot_file.write_text(content, encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to save snapshot: {e}")
                return None

            versions.append(version)
            self._versions[doc_id] = versions
            self._save_index()

            logger.info(f"Version {new_version_num} saved for {filename}")
            return version

    def list_versions(self, doc_id: str) -> list[DocumentVersion]:
        """
        List all versions of a document (newest first).

        Args:
            doc_id: Document ID

        Returns:
            List of DocumentVersion objects
        """
        versions = self._versions.get(doc_id, [])
        return sorted(versions, key=lambda v: -v.version)

    def get_version_content(self, doc_id: str, version: int) -> Optional[str]:
        """
        Get the content of a specific version.

        Args:
            doc_id: Document ID
            version: Version number (1-based)

        Returns:
            Content string if found, None otherwise
        """
        snapshot_file = self._versions_dir() / f"{doc_id}_v{version}.txt"
        if snapshot_file.exists():
            try:
                return snapshot_file.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def rollback(self, doc_id: str, version: int) -> Optional[str]:
        """
        Rollback a document to a previous version.

        Args:
            doc_id: Document ID
            version: Version number to rollback to

        Returns:
            The content of the rolled-back version, or None if failed
        """
        content = self.get_version_content(doc_id, version)
        if content is None:
            logger.warning(f"Version {version} not found for {doc_id}")
            return None

        # Add a new version with the rolled-back content
        versions = self._versions.get(doc_id, [])
        filename = versions[-1].filename if versions else "unknown"

        self.add_version(
            doc_id=doc_id,
            filename=filename,
            content=content,
            change_summary=f"Rolled back to version {version}",
        )

        logger.info(f"Rolled back {doc_id} to version {version}")
        return content

    def delete_doc_history(self, doc_id: str) -> int:
        """
        Delete all version history for a document.

        Args:
            doc_id: Document ID

        Returns:
            Number of versions deleted
        """
        with self._lock:
            versions = self._versions.pop(doc_id, [])
            count = len(versions)

            # Delete snapshot files
            for v in versions:
                snapshot_file = self._versions_dir() / f"{doc_id}_v{v.version}.txt"
                try:
                    if snapshot_file.exists():
                        snapshot_file.unlink()
                except Exception:
                    pass

            self._save_index()
            logger.info(f"Deleted {count} versions for {doc_id}")
            return count

    def get_stats(self) -> dict:
        """Get version tracker statistics."""
        with self._lock:
            total_versions = sum(len(v) for v in self._versions.values())
            return {
                "document_count": len(self._versions),
                "total_versions": total_versions,
                "avg_versions": round(total_versions / max(len(self._versions), 1), 1),
                "path": str(self._path),
            }
