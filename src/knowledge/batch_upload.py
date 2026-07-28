"""
Batch Document Upload (Feature #36) + Chunk Overlap Adjuster (Feature #38).
Adds directory scanning and configurable chunking to the KnowledgeBase.

Provides:
- Batch upload from a directory with recursion
- ChunkConfig dataclass for fine-grained control
- Progress tracking for batch operations
- File type filtering
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.core import setup_logger

logger = setup_logger("batch_upload")

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".md", ".csv", ".json"}


@dataclass
class ChunkConfig:
    """
    Configuration for text chunking (Feature #38).

    Allows users to adjust chunk size and overlap from the UI.

    Attributes:
        chunk_size: Target chunk size in characters (default: 500)
        chunk_overlap: Overlap between consecutive chunks (default: 100)
        use_paragraph_boundaries: Prefer breaking at paragraph boundaries (default: True)
    """
    chunk_size: int = 500
    chunk_overlap: int = 100
    use_paragraph_boundaries: bool = True

    def validate(self) -> None:
        """Validate config and raise ValueError if invalid."""
        if self.chunk_size < 50:
            raise ValueError("chunk_size must be at least 50 characters")
        if self.chunk_size > 5000:
            raise ValueError("chunk_size must be at most 5000 characters")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

    def to_dict(self) -> dict:
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "use_paragraph_boundaries": self.use_paragraph_boundaries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChunkConfig":
        return cls(
            chunk_size=int(data.get("chunk_size", 500)),
            chunk_overlap=int(data.get("chunk_overlap", 100)),
            use_paragraph_boundaries=bool(data.get("use_paragraph_boundaries", True)),
        )


@dataclass
class BatchUploadResult:
    """Result of a batch upload operation."""
    total_files: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    elapsed_ms: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"📁 **Batch Upload Complete**\n\n"
            f"- **Total files found:** {self.total_files}\n"
            f"- **✅ Successfully uploaded:** {self.successful}\n"
            f"- **⏭️ Skipped (already exist):** {self.skipped}\n"
            f"- **❌ Failed:** {self.failed}\n"
            f"- **Time:** {self.elapsed_ms:.0f}ms\n\n"
            f"{'⚠️ Errors:' if self.errors else '🎉 All done!'}\n"
            + "\n".join(f"  - {e[:100]}" for e in self.errors[:5])
        )


def scan_directory(
    directory_path: str,
    extensions: Optional[set[str]] = None,
    recursive: bool = True,
    max_files: int = 100,
) -> list[Path]:
    """
    Scan a directory for supported files.

    Args:
        directory_path: Path to scan
        extensions: Set of file extensions to include (default: all supported)
        recursive: Whether to scan subdirectories
        max_files: Maximum number of files to return

    Returns:
        List of file paths
    """
    exts = extensions or SUPPORTED_EXTENSIONS
    path = Path(directory_path)
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Directory not found: {directory_path}")

    files: list[Path] = []
    if recursive:
        iterator = path.rglob("*")
    else:
        iterator = path.glob("*")

    for f in iterator:
        if len(files) >= max_files:
            break
        if f.is_file() and f.suffix.lower() in exts:
            files.append(f)

    return files


def batch_upload(
    knowledge_base,
    directory_path: str,
    extensions: Optional[set[str]] = None,
    recursive: bool = True,
    max_files: int = 100,
    chunk_config: Optional[ChunkConfig] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> BatchUploadResult:
    """
    Upload all supported files from a directory to the knowledge base.

    Args:
        knowledge_base: KnowledgeBase instance (must have add_file method)
        directory_path: Directory to scan
        extensions: File extensions to include
        recursive: Whether to scan subdirectories
        max_files: Maximum files to upload
        chunk_config: Optional chunking configuration (Feature #38)
        progress_callback: Optional callback(current, total) for progress tracking

    Returns:
        BatchUploadResult with statistics
    """
    result = BatchUploadResult()
    start_time = time.time()

    try:
        files = scan_directory(directory_path, extensions, recursive, max_files)
    except FileNotFoundError as e:
        result.errors.append(str(e))
        result.elapsed_ms = (time.time() - start_time) * 1000
        return result

    result.total_files = len(files)

    cc = chunk_config or ChunkConfig()

    for i, file_path in enumerate(files):
        if progress_callback:
            progress_callback(i + 1, result.total_files)

        try:
            file_bytes = file_path.read_bytes()
            # Try with chunk params (ChromaDBKnowledgeBase), fall back to simple (SimpleKnowledgeBase)
            try:
                doc_id = knowledge_base.add_file(
                    str(file_path),
                    file_bytes,
                    chunk_size=cc.chunk_size,
                    chunk_overlap=cc.chunk_overlap,
                )
            except TypeError:
                logger.debug("KnowledgeBase does not support chunk params, using defaults")
                doc_id = knowledge_base.add_file(str(file_path), file_bytes)

            if doc_id:
                result.successful += 1
            else:
                result.skipped += 1
        except Exception as e:
            result.failed += 1
            result.errors.append(f"{file_path.name}: {e}")
            logger.warning(f"Batch upload failed for {file_path.name}: {e}")

    result.elapsed_ms = (time.time() - start_time) * 1000
    logger.info(
        f"Batch upload: {result.successful} ok, {result.skipped} skipped, "
        f"{result.failed} failed from {result.total_files} files "
        f"in {result.elapsed_ms:.0f}ms"
    )
    return result
