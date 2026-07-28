"""
Tests for Feature #39: Source Citation Highlight.
"""

import pytest

from src.core.source_citation import SourceCitationTracker, Citation

# Create a mock SearchResult-like object
class MockSearchResult:
    def __init__(self, doc_id, filename, content, score=0.5, chunk_index=0):
        self.doc_id = doc_id
        self.filename = filename
        self.content = content
        self.score = score
        self.chunk_index = chunk_index


class TestSourceCitationTracker:
    """Tests for SourceCitationTracker class."""

    def test_add_citation(self):
        tracker = SourceCitationTracker()
        cid = tracker.add_citation(
            doc_id="doc_1",
            filename="report.pdf",
            chunk_text="Revenue increased by 20% in Q1.",
            score=0.85,
            chunk_index=0,
        )
        assert cid is not None
        citation = tracker.get_citation(cid)
        assert citation is not None
        assert citation.filename == "report.pdf"

    def test_deduplicate_same_chunk(self):
        tracker = SourceCitationTracker()
        cid1 = tracker.add_citation(
            doc_id="doc_1", filename="r.pdf", chunk_text="Q1 results", chunk_index=0,
        )
        cid2 = tracker.add_citation(
            doc_id="doc_1", filename="r.pdf", chunk_text="Q1 results", chunk_index=0,
        )
        assert cid1 == cid2  # Same ID returned

    def test_add_citation_from_search(self):
        tracker = SourceCitationTracker()
        result = MockSearchResult("doc_1", "report.pdf", "Q1 revenue up 20%", 0.9)
        cid = tracker.add_citation_from_search(result)
        assert cid is not None

    def test_get_citations_for_response(self):
        tracker = SourceCitationTracker()
        tracker.add_citation(doc_id="d1", filename="r1.pdf", chunk_text="Python is great for AI", score=0.8)
        tracker.add_citation(doc_id="d2", filename="r2.pdf", chunk_text="JavaScript for web", score=0.7)
        citations = tracker.get_citations_for_response("Python AI")
        assert len(citations) >= 1
        assert any("Python" in c.chunk_text for c in citations)

    def test_get_citations_for_response_empty(self):
        tracker = SourceCitationTracker()
        citations = tracker.get_citations_for_response("test")
        assert citations == []

    def test_get_citations_by_session(self):
        tracker = SourceCitationTracker()
        tracker.add_citation(doc_id="d1", filename="r1.pdf", chunk_text="text", session_id="s1")
        tracker.add_citation(doc_id="d2", filename="r2.pdf", chunk_text="more text", session_id="s2")
        citations = tracker.get_citations_by_session("s1")
        assert len(citations) == 1

    def test_get_citations_by_document(self):
        tracker = SourceCitationTracker()
        tracker.add_citation(doc_id="doc_a", filename="a.pdf", chunk_text="chunk 0", chunk_index=0)
        tracker.add_citation(doc_id="doc_a", filename="a.pdf", chunk_text="chunk 1", chunk_index=1)
        tracker.add_citation(doc_id="doc_b", filename="b.pdf", chunk_text="other", chunk_index=0)
        citations = tracker.get_citations_by_document("doc_a")
        assert len(citations) == 2

    def test_format_citation_markdown(self):
        tracker = SourceCitationTracker()
        cid = tracker.add_citation(doc_id="d1", filename="r.pdf", chunk_text="Important result", score=0.9)
        citation = tracker.get_citation(cid)
        md = tracker.format_citation_markdown(citation, index=1)
        assert "[1]" in md
        assert "r.pdf" in md

    def test_format_citations_markdown_empty(self):
        tracker = SourceCitationTracker()
        md = tracker.format_citations_markdown([])
        assert md == ""

    def test_format_citations_markdown_with_citations(self):
        tracker = SourceCitationTracker()
        cid1 = tracker.add_citation(doc_id="d1", filename="r1.pdf", chunk_text="Result A", score=0.9)
        cid2 = tracker.add_citation(doc_id="d2", filename="r2.pdf", chunk_text="Result B", score=0.8)
        citations = [tracker.get_citation(cid1), tracker.get_citation(cid2)]
        md = tracker.format_citations_markdown(citations)
        assert "r1.pdf" in md
        assert "r2.pdf" in md
        assert "Sources" in md

    def test_format_inline_citation(self):
        tracker = SourceCitationTracker()
        cid = tracker.add_citation(doc_id="d1", filename="doc.pdf", chunk_text="text")
        citation = tracker.get_citation(cid)
        inline = tracker.format_inline_citation(citation)
        assert "doc.pdf" in inline

    def test_citation_preview(self):
        c = Citation(doc_id="d1", filename="f.pdf", chunk_text="A" * 200)
        preview = c.preview
        assert len(preview) <= 85  # 80 + "..."
        assert preview.endswith("...")

    def test_citation_source_label(self):
        c = Citation(doc_id="d1", filename="report.pdf", chunk_text="text", page_number=5)
        assert "report.pdf" in c.source_label
        assert "p.5" in c.source_label

    def test_clear_citations(self):
        tracker = SourceCitationTracker()
        tracker.add_citation(doc_id="d1", filename="f.pdf", chunk_text="text")
        assert tracker.get_stats()["total_citations"] == 1
        tracker.clear()
        assert tracker.get_stats()["total_citations"] == 0

    def test_get_stats(self):
        tracker = SourceCitationTracker()
        tracker.add_citation(doc_id="d1", filename="f.pdf", chunk_text="text")
        stats = tracker.get_stats()
        assert stats["total_citations"] == 1
        assert stats["unique_documents"] == 1

    def test_trim_lowest(self):
        tracker = SourceCitationTracker(max_citations=2)
        tracker.add_citation(doc_id="d1", filename="f1.pdf", chunk_text="low score content", score=0.1)
        tracker.add_citation(doc_id="d2", filename="f2.pdf", chunk_text="high score content", score=0.9)
        tracker.add_citation(doc_id="d3", filename="f3.pdf", chunk_text="medium score content", score=0.5)
        # Should keep 2 highest
        assert tracker.get_stats()["total_citations"] <= 2

    def test_html_highlight(self):
        tracker = SourceCitationTracker()
        cid = tracker.add_citation(doc_id="d1", filename="f.pdf", chunk_text="Revenue increased by 20%")
        citations = [tracker.get_citation(cid)]
        html = tracker.format_html_highlight("The Revenue increased by 20% this quarter.", citations)
        assert "mark" in html or "citation" in html
