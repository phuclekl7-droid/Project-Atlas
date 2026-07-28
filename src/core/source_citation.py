"""
Source Citation Highlight (Feature #39).
Tracks and formats source citations for RAG results.

Provides:
- Citation metadata tracking per chunk
- Formatted citation text (Markdown)
- Source document reference management
- Highlight annotation for cited passages

Usage:
    tracker = SourceCitationTracker()
    tracker.add_citation(doc_id="abc", filename="report.pdf", chunk="Revenue increased...", page=3)
    citations = tracker.get_citations_for_response("Revenue increased by 20%")
    markdown = tracker.format_citations_markdown(citations)
"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core import setup_logger

logger = setup_logger("source_citation")


@dataclass
class Citation:
    """
    A single source citation.

    Attributes:
        id: Unique citation ID
        doc_id: Source document ID
        filename: Source filename (for display)
        chunk_text: The cited text content
        score: Relevance score (0.0 to 1.0)
        chunk_index: Index of chunk in document
        page_number: Optional page number for PDFs
        timestamp: When the citation was created
        metadata: Additional metadata (author, date, title)
    """

    id: str = ""
    doc_id: str = ""
    filename: str = ""
    chunk_text: str = ""
    score: float = 0.0
    chunk_index: int = 0
    page_number: Optional[int] = None
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            unique = f"{self.doc_id}:{self.chunk_index}:{self.filename}:{self.chunk_text[:50]}"
            self.id = hashlib.md5(unique.encode()).hexdigest()[:12]

    @property
    def preview(self) -> str:
        """Get a short preview of the citation text."""
        text = self.chunk_text[:80].replace("\n", " ")
        if len(self.chunk_text) > 80:
            text += "..."
        return text

    @property
    def source_label(self) -> str:
        """Get a human-readable source label (e.g., 'report.pdf §3')."""
        label = self.filename
        if self.page_number is not None:
            label += f" (p.{self.page_number})"
        return label


class SourceCitationTracker:
    """
    Tracks source citations from RAG results.

    Integrates with KnowledgeBase search results to create
    structured citations that can be displayed alongside AI responses.

    Usage:
        tracker = SourceCitationTracker()

        # Add citations from search results
        for result in search_results:
            tracker.add_citation_from_search(result)

        # Get citations most relevant to a response
        citations = tracker.get_citations_for_response(response_text)

        # Format as Markdown
        md = tracker.format_citations_markdown(citations)
    """

    def __init__(self, max_citations: int = 50):
        """
        Initialize the citation tracker.

        Args:
            max_citations: Maximum citations to store
        """
        self._citations: dict[str, Citation] = {}
        self._max_citations = max_citations
        self._session_refs: dict[str, set[str]] = {}  # session_id -> set of citation_ids

    def add_citation(
        self,
        doc_id: str,
        filename: str,
        chunk_text: str,
        score: float = 0.0,
        chunk_index: int = 0,
        page_number: Optional[int] = None,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Add a citation to the tracker.

        Args:
            doc_id: Source document ID
            filename: Source filename
            chunk_text: The cited text content
            score: Relevance score
            chunk_index: Chunk index in document
            page_number: Optional page number
            metadata: Additional metadata
            session_id: Optional session ID for grouping

        Returns:
            Citation ID
        """
        citation = Citation(
            doc_id=doc_id,
            filename=filename,
            chunk_text=chunk_text,
            score=score,
            chunk_index=chunk_index,
            page_number=page_number,
            timestamp=time.time(),
            metadata=metadata or {},
        )

        # Deduplicate by looking for similar content from same doc
        existing_id = None
        for cid, c in self._citations.items():
            if c.doc_id == doc_id and c.chunk_index == chunk_index:
                # Update existing
                c.score = max(c.score, score)
                c.timestamp = time.time()
                c.metadata.update(metadata or {})
                existing_id = cid
                break

        if existing_id:
            return existing_id

        # Add new citation
        self._citations[citation.id] = citation

        # Track session reference
        if session_id:
            if session_id not in self._session_refs:
                self._session_refs[session_id] = set()
            self._session_refs[session_id].add(citation.id)

        # Trim old/low-score citations
        if len(self._citations) > self._max_citations:
            self._trim_lowest()

        return citation.id

    def add_citation_from_search(
        self,
        search_result,
        session_id: Optional[str] = None,
    ) -> str:
        """Add a citation from a KnowledgeBase SearchResult object."""
        return self.add_citation(
            doc_id=search_result.doc_id,
            filename=search_result.filename,
            chunk_text=search_result.content,
            score=search_result.score,
            chunk_index=search_result.chunk_index,
            session_id=session_id,
        )

    def get_citation(self, citation_id: str) -> Optional[Citation]:
        """Get a specific citation by ID."""
        return self._citations.get(citation_id)

    def get_citations_for_response(
        self,
        response_text: str,
        max_citations: int = 5,
        min_score: float = 0.0,
    ) -> list[Citation]:
        """
        Get citations relevant to a response text.

        Uses simple keyword overlap to find relevant citations.
        Returns sorted by relevance score.

        Args:
            response_text: The AI response text to match against
            max_citations: Maximum citations to return
            min_score: Minimum relevance score

        Returns:
            List of Citation objects
        """
        if not response_text or not self._citations:
            return []

        # Tokenize response
        response_words = set(response_text.lower().split())
        if not response_words:
            return []

        # Score citations by word overlap
        scored = []
        for citation in self._citations.values():
            if citation.score < min_score:
                continue

            citation_words = set(citation.chunk_text.lower().split())
            if not citation_words:
                continue

            overlap = len(response_words & citation_words)
            if overlap > 0:
                # Combined score: original relevance + word overlap
                combined = citation.score * 0.6 + (overlap / len(response_words)) * 0.4
                scored.append((combined, citation))

        # Sort by combined score
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:max_citations]]

    def get_citations_by_session(self, session_id: str) -> list[Citation]:
        """Get all citations referenced in a session."""
        refs = self._session_refs.get(session_id, set())
        return [self._citations[cid] for cid in refs if cid in self._citations]

    def get_citations_by_document(self, doc_id: str) -> list[Citation]:
        """Get all citations from a specific document."""
        return sorted(
            [c for c in self._citations.values() if c.doc_id == doc_id],
            key=lambda c: c.chunk_index,
        )

    # ── Formatting ──

    def format_citation_markdown(self, citation: Citation, index: int = 1) -> str:
        """
        Format a single citation as Markdown.

        Returns a string like:
            [1] report.pdf §3 — "Revenue increased by 20%..."
        """
        parts = [f"[{index}] **{citation.source_label}**"]

        if citation.score > 0:
            parts.append(f"(score: {citation.score:.2f})")

        parts.append("")
        parts.append(f"> {citation.preview}")

        return " ".join(parts)

    def format_citations_markdown(
        self,
        citations: list[Citation],
        title: str = "📚 Sources",
    ) -> str:
        """
        Format multiple citations as a Markdown section.

        Args:
            citations: List of Citation objects
            title: Section title

        Returns:
            Markdown formatted citations section
        """
        if not citations:
            return ""

        lines = [f"### {title}", ""]
        for i, citation in enumerate(citations, 1):
            lines.append(self.format_citation_markdown(citation, i))
            lines.append("")

        # Add source summary
        sources = set(c.filename for c in citations)
        lines.append(f"*Citations from {len(sources)} document(s)*")
        lines.append("")

        return "\n".join(lines)

    def format_inline_citation(self, citation: Citation) -> str:
        """Format a citation as an inline reference."""
        return f"[[{citation.source_label}]({citation.id})]"

    def format_html_highlight(
        self,
        text: str,
        citations: list[Citation],
    ) -> str:
        """
        Highlight text passages that match citations with HTML markers.

        Args:
            text: The text to annotate
            citations: Citations to highlight

        Returns:
            HTML string with highlighted spans
        """
        highlighted = text
        for i, citation in enumerate(citations, 1):
            # Find key phrases from citation in text (simple approach)
            words = citation.chunk_text.split()
            if len(words) >= 5:
                # Use first and last few words as anchor
                phrase = " ".join(words[:8])
                if phrase in highlighted:
                    highlighted = highlighted.replace(
                        phrase,
                        f'<mark class="citation-source" data-citation="{i}">'
                        f'{phrase}</mark>',
                        1,
                    )
        return highlighted

    # ── Management ──

    def clear(self) -> int:
        """Clear all citations. Returns count cleared."""
        count = len(self._citations)
        self._citations.clear()
        self._session_refs.clear()
        return count

    def get_stats(self) -> dict:
        """Get citation tracker statistics."""
        return {
            "total_citations": len(self._citations),
            "unique_documents": len(set(c.doc_id for c in self._citations.values())),
            "sessions_with_refs": len(self._session_refs),
        }

    def _trim_lowest(self) -> None:
        """Remove the lowest-scored citations when over capacity."""
        if len(self._citations) <= self._max_citations:
            return

        sorted_citations = sorted(
            self._citations.items(),
            key=lambda x: x[1].score,
        )
        # Remove bottom 20%
        remove_count = max(1, len(sorted_citations) - self._max_citations)
        for cid, _ in sorted_citations[:remove_count]:
            del self._citations[cid]
            # Also clean session refs
            for session_refs in self._session_refs.values():
                session_refs.discard(cid)
