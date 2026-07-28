"""Tests for Hybrid Search (Feature 15)."""

import pytest
from src.core.hybrid_search import BM25Index, HybridSearch, HybridResult


class TestBM25Index:
    """Test BM25 sparse search index."""

    def test_add_and_build(self):
        index = BM25Index()
        index.add_document("doc1", "Python is a programming language")
        index.add_document("doc2", "JavaScript is for web development")
        index.build()
        assert index.document_count == 2

    def test_search_finds_results(self):
        index = BM25Index()
        index.add_document("doc1", "Python is a programming language")
        index.add_document("doc2", "JavaScript is for web development")
        results = index.search("programming language")
        assert len(results) > 0

    def test_search_returns_sorted(self):
        index = BM25Index()
        index.add_document("doc1", "Python programming language")
        index.add_document("doc2", "JavaScript web development")
        index.add_document("doc3", "Python is great for programming")
        results = index.search("Python programming")
        assert len(results) > 0
        # First result should be most relevant
        assert results[0][1] >= results[-1][1] if len(results) > 1 else True

    def test_empty_index(self):
        index = BM25Index()
        results = index.search("test")
        assert results == []

    def test_add_multiple_documents(self):
        index = BM25Index()
        index.add_documents([
            ("doc1", "Python is great"),
            ("doc2", "Java is also good"),
        ])
        assert index.document_count == 2

    def test_clear(self):
        index = BM25Index()
        index.add_document("doc1", "Python")
        assert index.document_count == 1
        index.clear()
        assert index.document_count == 0


class TestHybridSearch:
    """Test hybrid search combining BM25 + vector."""

    def test_bm25_only_no_vector_fn(self):
        hybrid = HybridSearch(vector_search_fn=None)
        hybrid.add_documents([
            {"id": "doc1", "content": "Python is a programming language"},
            {"id": "doc2", "content": "JavaScript for web"},
        ])
        results = hybrid.search("Python programming")
        assert len(results) > 0
        assert all(isinstance(r, HybridResult) for r in results)

    def test_empty_query(self):
        hybrid = HybridSearch()
        results = hybrid.search("")
        assert results == []

    def test_get_stats(self):
        hybrid = HybridSearch()
        stats = hybrid.get_stats()
        assert "total_documents" in stats
        assert stats["total_documents"] == 0

    def test_added_documents_in_stats(self):
        hybrid = HybridSearch()
        hybrid.add_documents([
            {"id": "doc1", "content": "Python programming"},
        ])
        stats = hybrid.get_stats()
        assert stats["total_documents"] == 1

    def test_hybrid_result_attributes(self):
        hybrid = HybridSearch()
        hybrid.add_documents([
            {"id": "doc1", "content": "Python programming language"},
        ])
        results = hybrid.search("Python")
        if results:
            r = results[0]
            assert isinstance(r.doc_id, str)
            assert isinstance(r.content, str)
            assert isinstance(r.score, float)
