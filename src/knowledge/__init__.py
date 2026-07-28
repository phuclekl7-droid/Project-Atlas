"""
Knowledge module: Manages RAG (Retrieval-Augmented Generation) with ChromaDB vector store.

Provides:
- Text chunking and processing for uploaded files
- ChromaDB vector storage for semantic search
- Integration with Workflow for context injection
- Local folder auto-indexer (watchdog-based)

Usage:
    kb = KnowledgeBase(path="data/knowledge")
    doc_id = kb.add_text("path/to/file.txt", "File content here...")
    results = kb.search("What does this document say?")
"""

import hashlib
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from src.core import setup_logger

logger = setup_logger("knowledge")


# ── Optional watchdog for folder auto-indexing ──
_HAVE_WATCHDOG = False
_WATCHDOG_OBSERVER = None
_WATCHDOG_THREAD = None

try:
    from watchdog.observers import Observer as WatchdogObserver
    from watchdog.events import FileSystemEventHandler
    _HAVE_WATCHDOG = True
except ImportError:
    WatchdogObserver = None
    FileSystemEventHandler = object


# ============================================================
# File Extraction (PDF, DOCX, TXT)
# ============================================================

# Supported file extensions and their descriptions
SUPPORTED_EXTENSIONS = {
    ".txt": "Plain Text",
    ".pdf": "PDF Document",
    ".docx": "Word Document",
}


# Optional imports for PDF and DOCX processing
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF file using pypdf.

    Args:
        file_bytes: Raw PDF file bytes

    Returns:
        Extracted text, or empty string on failure
    """
    if PdfReader is None:
        logger.warning("pypdf not installed. Run: pip install pypdf")
        return ""
    try:
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    except Exception as e:
        logger.warning(f"Failed to extract text from PDF: {e}")
        return ""


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extract text from a DOCX file using python-docx.

    Args:
        file_bytes: Raw DOCX file bytes

    Returns:
        Extracted text, or empty string on failure
    """
    if Document is None:
        logger.warning("python-docx not installed. Run: pip install python-docx")
        return ""
    try:
        import io
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.warning(f"Failed to extract text from DOCX: {e}")
        return ""


def extract_text_from_file(filename: str, file_bytes: bytes) -> str:
    """
    Extract text from a file based on its extension.

    Supports: .txt, .pdf, .docx

    Args:
        filename: Original filename (used to detect type)
        file_bytes: Raw file bytes

    Returns:
        Extracted text content, or empty string on failure
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext == ".docx":
        return extract_text_from_docx(file_bytes)
    elif ext == ".txt":
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_bytes.decode("latin-1")
            except Exception:
                logger.warning(f"Cannot decode text file: {filename}")
                return ""
    else:
        logger.warning(f"Unsupported file type: {ext} for {filename}")
        return ""


# ============================================================
# Text Chunking
# ============================================================


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping chunks for vector storage.

    Splits on paragraph boundaries first, then sentences,
    then falls back to character-level splitting.

    Args:
        text: Raw text to chunk
        chunk_size: Target chunk size in characters
        overlap: Overlap between consecutive chunks in characters

    Returns:
        List of text chunks
    """
    if not text.strip():
        return []

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break at a paragraph boundary
        if end < text_len:
            # Look backward for paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + chunk_size // 2:
                end = para_break
            else:
                # Look backward for sentence break
                for sep in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
                    sentence_break = text.rfind(sep, start, end)
                    if sentence_break > start + chunk_size // 2:
                        end = sentence_break + len(sep)
                        break
                else:
                    # Look backward for space
                    space_break = text.rfind(" ", start, end)
                    if space_break > start + chunk_size // 2:
                        end = space_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward (with overlap)
        start = end - overlap if end - overlap > start + 1 else end

        if start >= text_len:
            break

    # If no chunks were created (e.g., text too short), use the whole text
    if not chunks and text.strip():
        chunks.append(text.strip())

    logger.debug(f"Chunked {text_len} chars into {len(chunks)} chunks")
    return chunks


# ============================================================
# Data Model
# ============================================================


@dataclass
class KnowledgeDoc:
    """
    Represents a document stored in the knowledge base.

    Attributes:
        id: Unique document identifier (SHA256 of filename)
        filename: Original filename
        chunks: List of text chunks
        chunk_count: Number of chunks
        char_count: Total character count
    """

    id: str
    filename: str
    chunks: list[str] = field(default_factory=list)
    chunk_count: int = 0
    char_count: int = 0


@dataclass
class SearchResult:
    """
    Result from a knowledge base search.

    Attributes:
        content: The matched text chunk
        doc_id: Source document ID
        filename: Source filename
        score: Similarity score (higher = more relevant)
        chunk_index: Index of the chunk within the document
    """

    content: str
    doc_id: str
    filename: str
    score: float = 0.0
    chunk_index: int = 0

    def __repr__(self) -> str:
        preview = self.content[:60].replace("\n", " ")
        return f"SearchResult(doc={self.filename!r}, score={self.score:.3f}, content={preview!r})"


# ============================================================
# ChromaDB Knowledge Base
# ============================================================


class ChromaDBKnowledgeBase:
    """
    Vector-based knowledge base using ChromaDB for semantic search.

    Stores document chunks as embeddings for RAG (Retrieval-Augmented Generation).

    Usage:
        kb = ChromaDBKnowledgeBase(path="data/knowledge")
        kb.add_text("report.txt", "Q1 revenue increased by 20%...")
        results = kb.search("financial results")
    """

    def __init__(self, path: str = "data/knowledge"):
        self.path = str(path)
        self._collection = None
        self._client = None

        # Ensure directory exists
        Path(self.path).mkdir(parents=True, exist_ok=True)

        self._initialize()
        logger.info(f"KnowledgeBase initialized: {self.path}")

    def _initialize(self):
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.path)
            # Use or create collection
            self._collection = self._client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            logger.debug(f"ChromaDB collection ready: {self._collection.count()} docs")
        except ImportError:
            logger.warning("chromadb not installed. Run: pip install chromadb")
            self._client = None
            self._collection = None
        except Exception as e:
            logger.warning(f"Failed to initialize ChromaDB: {e}")
            self._client = None
            self._collection = None

    @property
    def available(self) -> bool:
        """Whether ChromaDB is available and initialized."""
        return self._collection is not None

    # ── Document Management ──

    def _normalize_filename(self, filename: str) -> str:
        """Normalize path separators to forward slashes for cross-platform consistency."""
        return Path(filename).as_posix()

    def add_file(self, filename: str, file_bytes: bytes, chunk_size: int = 500, chunk_overlap: int = 100) -> Optional[str]:
        """
        Add a file to the knowledge base by extracting text based on type.

        Supports: .txt, .pdf, .docx

        Args:
            filename: Original filename (extension used to detect type)
            file_bytes: Raw file bytes
            chunk_size: Target chunk size in characters (Feature 159)
            chunk_overlap: Overlap between chunks (Feature 159)

        Returns:
            Document ID if successful, None if failed
        """
        if not file_bytes:
            logger.warning(f"Empty file: {filename}")
            return None

        normalized = self._normalize_filename(filename)
        text = extract_text_from_file(normalized, file_bytes)
        if not text.strip():
            logger.warning(f"No text extracted from {filename}")
            return None

        return self.add_text(normalized, text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    def add_text(self, filename: str, text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> Optional[str]:
        """
        Add a text document to the knowledge base.

        The text is automatically chunked and each chunk is embedded and stored.

        Args:
            filename: Original filename (for reference)
            text: Document text content

        Returns:
            Document ID if successful, None if failed
        """
        if not self.available:
            logger.warning("ChromaDB not available, cannot add document")
            return None

        if not text.strip():
            logger.warning(f"Empty text for {filename}, skipping")
            return None

        # Normalize path separators for cross-platform consistency
        filename = self._normalize_filename(filename)

        # Generate document ID
        doc_id = hashlib.sha256(f"{filename}:{text[:100]}".encode()).hexdigest()[:16]

        # Check if document already exists
        existing = self._collection.get(ids=[doc_id])
        if existing and existing["ids"]:
            logger.info(f"Document '{filename}' already exists, skipping")
            return doc_id

        # Chunk text with configurable size/overlap (Feature 159)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

        if not chunks:
            logger.warning(f"No chunks created for {filename}")
            return None

        # Generate chunk IDs and metadata
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"doc_id": doc_id, "filename": filename, "chunk_index": i}
            for i in range(len(chunks))
        ]

        try:
            self._collection.add(
                documents=chunks,
                ids=chunk_ids,
                metadatas=metadatas,
            )
            logger.info(f"Added '{filename}': {len(chunks)} chunks, {len(text)} chars")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to add document '{filename}': {e}")
            return None

    def search(self, query: str, n_results: int = 3) -> list[SearchResult]:
        """
        Search the knowledge base for relevant chunks.

        Args:
            query: The search query (natural language)
            n_results: Maximum number of results to return

        Returns:
            List of SearchResult objects, ordered by relevance (highest first)
        """
        if not self.available:
            return []

        if not query.strip():
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
            )

            if not results or not results["ids"] or not results["ids"][0]:
                return []

            search_results = []
            for i in range(len(results["ids"][0])):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                search_results.append(SearchResult(
                    content=results["documents"][0][i],
                    doc_id=metadata.get("doc_id", ""),
                    filename=metadata.get("filename", "unknown"),
                    score=results["distances"][0][i] if results.get("distances") else 0.0,
                    chunk_index=metadata.get("chunk_index", 0),
                ))

            logger.debug(f"Search '{query[:50]}': {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def list_documents(self) -> list[KnowledgeDoc]:
        """
        List all documents in the knowledge base.

        Returns:
            List of KnowledgeDoc objects
        """
        if not self.available:
            return []

        try:
            # Get unique doc_ids from metadata
            all_data = self._collection.get(include=["metadatas"])
            if not all_data or not all_data["ids"]:
                return []

            # Group by document
            doc_map: dict[str, dict] = {}
            for i, doc_id in enumerate(all_data["ids"]):
                meta = all_data["metadatas"][i] if all_data["metadatas"] else {}
                source_id = meta.get("doc_id", "unknown")
                filename = meta.get("filename", "unknown")

                if source_id not in doc_map:
                    doc_map[source_id] = {
                        "id": source_id,
                        "filename": filename,
                        "chunks": [],
                        "chunk_count": 0,
                        "char_count": 0,
                    }
                doc_map[source_id]["chunk_count"] += 1
                if all_data["documents"]:
                    doc_map[source_id]["char_count"] += len(all_data["documents"][i])

            return [
                KnowledgeDoc(
                    id=info["id"],
                    filename=info["filename"],
                    chunk_count=info["chunk_count"],
                    char_count=info["char_count"],
                )
                for info in doc_map.values()
            ]

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document and all its chunks.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if successful
        """
        if not self.available:
            return False

        try:
            # Delete all chunks with matching doc_id
            all_data = self._collection.get(include=["metadatas"])
            if not all_data or not all_data["ids"]:
                return False

            ids_to_delete = [
                all_data["ids"][i]
                for i in range(len(all_data["ids"]))
                if all_data["metadatas"]
                and all_data["metadatas"][i].get("doc_id") == doc_id
            ]

            if ids_to_delete:
                self._collection.delete(ids=ids_to_delete)
                logger.info(f"Deleted document {doc_id}: {len(ids_to_delete)} chunks")

            return True

        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False

    def delete_all(self) -> int:
        """Delete all documents. Returns number of deleted chunks."""
        if not self.available:
            return 0

        try:
            count = self._collection.count()
            self._collection.delete(where={})
            logger.info(f"Deleted all documents: {count} chunks")
            return count
        except Exception as e:
            logger.error(f"Failed to delete all: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        if not self.available:
            return {"available": False, "chunks": 0, "documents": 0, "path": self.path}

        try:
            chunk_count = self._collection.count()
            docs = self.list_documents()
            return {
                "available": True,
                "chunks": chunk_count,
                "documents": len(docs),
                "path": self.path,
            }
        except Exception as e:
            return {"available": False, "chunks": 0, "documents": 0, "error": str(e)}


# ── Simple in-memory fallback when ChromaDB is not available ──

class SimpleKnowledgeBase:
    """
    Simple keyword-based knowledge base as fallback when ChromaDB is not available.

    Uses basic keyword matching instead of vector search.
    """

    def __init__(self, path: str = "data/knowledge"):
        self.path = str(path)
        Path(self.path).mkdir(parents=True, exist_ok=True)
        self._docs: dict[str, KnowledgeDoc] = {}
        self._all_chunks: list[dict] = []
        logger.info(f"SimpleKnowledgeBase initialized (no ChromaDB): {self.path}")

    @property
    def available(self) -> bool:
        return True

    def _normalize_filename(self, filename: str) -> str:
        """Normalize path separators to forward slashes for cross-platform consistency."""
        return Path(filename).as_posix()

    def add_file(self, filename: str, file_bytes: bytes) -> Optional[str]:
        """Add a file to the knowledge base by extracting text based on type."""
        if not file_bytes:
            logger.warning(f"Empty file: {filename}")
            return None
        normalized = self._normalize_filename(filename)
        text = extract_text_from_file(normalized, file_bytes)
        if not text.strip():
            logger.warning(f"No text extracted from {filename}")
            return None
        return self.add_text(normalized, text)

    def add_text(self, filename: str, text: str) -> Optional[str]:
        if not text.strip():
            logger.warning(f"Empty text for {filename}, skipping")
            return None

        # Normalize path separators for cross-platform consistency
        filename = self._normalize_filename(filename)

        doc_id = hashlib.sha256(f"{filename}:{text[:100]}".encode()).hexdigest()[:16]

        if doc_id in self._docs:
            return doc_id

        chunks = chunk_text(text)
        doc = KnowledgeDoc(
            id=doc_id,
            filename=filename,
            chunks=chunks,
            chunk_count=len(chunks),
            char_count=len(text),
        )
        self._docs[doc_id] = doc

        for i, chunk in enumerate(chunks):
            self._all_chunks.append({
                "content": chunk,
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
            })

        return doc_id

    def search(self, query: str, n_results: int = 3) -> list[SearchResult]:
        if not query.strip() or not self._all_chunks:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for chunk_data in self._all_chunks:
            chunk_lower = chunk_data["content"].lower()
            # Count keyword matches
            score = sum(1 for word in query_words if word in chunk_lower)
            if score > 0:
                scored.append((score, chunk_data))

        # Sort by score descending
        scored.sort(key=lambda x: -x[0])

        results = []
        for score, data in scored[:n_results]:
            results.append(SearchResult(
                content=data["content"],
                doc_id=data["doc_id"],
                filename=data["filename"],
                score=score / len(query_words) if query_words else 0,
                chunk_index=data["chunk_index"],
            ))

        return results

    def list_documents(self) -> list[KnowledgeDoc]:
        return list(self._docs.values())

    def delete_document(self, doc_id: str) -> bool:
        if doc_id in self._docs:
            del self._docs[doc_id]
            self._all_chunks = [c for c in self._all_chunks if c["doc_id"] != doc_id]
            return True
        return False

    def delete_all(self) -> int:
        count = len(self._all_chunks)
        self._docs.clear()
        self._all_chunks.clear()
        return count

    def get_stats(self) -> dict:
        return {
            "available": True,
            "chunks": len(self._all_chunks),
            "documents": len(self._docs),
            "path": self.path,
        }


# ============================================================
# Local Folder Auto-Indexer (watchdog-based)
# ============================================================


class FolderIndexerHandler(FileSystemEventHandler):
    """
    Watchdog event handler that auto-indexes new files into the knowledge base.

    Fires when files are created or modified in the watched directory.
    Debounces rapid events (e.g., during file download).
    """

    def __init__(self, knowledge_base, extensions: tuple = (".txt", ".pdf", ".docx"), debounce_sec: float = 2.0):
        self.kb = knowledge_base
        self.extensions = extensions
        self.debounce_sec = debounce_sec
        self._last_events: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._process_file(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self._process_file(event.dest_path)

    def _process_file(self, file_path: str):
        """Process a single file after debounce."""
        path = Path(file_path)
        if path.suffix.lower() not in self.extensions:
            return

        # Debounce: ignore rapid repeated events
        now = time.time()
        last = self._last_events.get(file_path, 0)
        if now - last < self.debounce_sec:
            return
        self._last_events[file_path] = now

        try:
            file_bytes = path.read_bytes()
            if not file_bytes:
                return

            # Use the relative filename from the watched root
            # The kb already deduplicates by content hash
            result = self.kb.add_file(path.name, file_bytes)
            if result:
                logger.info(f"🌐 Auto-indexed: {path.name}")
            else:
                logger.debug(f"Auto-index skipped (already exists or empty): {path.name}")
        except Exception as e:
            logger.warning(f"Auto-index failed for {path.name}: {e}")


class FolderWatcher:
    """
    Manages a watchdog observer for auto-indexing a local folder.

    Usage:
        watcher = FolderWatcher("~/Atlas_Docs", kb)
        watcher.start()
        ...
        watcher.stop()
    """

    def __init__(
        self,
        folder_path: str,
        knowledge_base,
        extensions: tuple = (".txt", ".pdf", ".docx"),
        recursive: bool = True,
    ):
        if not _HAVE_WATCHDOG:
            raise ImportError(
                "watchdog is required for folder auto-indexing. "
                "Install: pip install watchdog"
            )

        self.folder_path = str(folder_path)
        self.knowledge_base = knowledge_base
        self.extensions = extensions
        self.recursive = recursive
        self._observer: Optional[WatchdogObserver] = None
        self._running = False

    def start(self):
        """Start watching the folder for new/modified files."""
        if self._running:
            logger.warning(f"FolderWatcher already running for {self.folder_path}")
            return

        folder = Path(self.folder_path)
        folder.mkdir(parents=True, exist_ok=True)

        handler = FolderIndexerHandler(
            self.knowledge_base,
            extensions=self.extensions,
        )

        self._observer = WatchdogObserver()
        self._observer.schedule(
            handler,
            str(folder),
            recursive=self.recursive,
        )
        self._observer.start()
        self._running = True
        logger.info(f"📁 FolderWatcher started: {self.folder_path}")

    def stop(self):
        """Stop watching the folder."""
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._running = False
            logger.info(f"📁 FolderWatcher stopped: {self.folder_path}")

    def is_running(self) -> bool:
        return self._running

    def __del__(self):
        self.stop()


def is_watchdog_available() -> bool:
    """Check if watchdog library is installed."""
    return _HAVE_WATCHDOG


def create_knowledge_base(path: str = "data/knowledge") -> Union[ChromaDBKnowledgeBase, "SimpleKnowledgeBase"]:
    """
    Factory function: try ChromaDB first, fall back to SimpleKnowledgeBase.

    Usage:
        kb = create_knowledge_base()
        kb.add_text("file.txt", "content")
    """
    try:
        import chromadb
        kb = ChromaDBKnowledgeBase(path=path)
        if kb.available:
            return kb
    except ImportError:
        logger.info("chromadb not installed, using SimpleKnowledgeBase")
    except Exception as e:
        logger.warning(f"ChromaDB init failed: {e}, using SimpleKnowledgeBase")

    return SimpleKnowledgeBase(path=path)
