"""
Tests for Feature #13: GraphRAG.
"""

import tempfile
from pathlib import Path

import pytest

from src.core.graph_rag import GraphRAG, _extract_entities


class TestExtractEntities:
    def test_extract_capitalized(self):
        entities = _extract_entities("Python and Machine Learning are popular")
        names = [e[0] for e in entities]
        assert any("Machine Learning" in n for n in names)

    def test_extract_technical_terms(self):
        entities = _extract_entities("The API uses REST and JSON")
        names = [e[0] for e in entities]
        assert any("API" in n for n in names)

    def test_empty_text(self):
        entities = _extract_entities("")
        assert entities == []

    def test_skip_stop_words(self):
        entities = _extract_entities("the and for with this is a test")
        assert len(entities) <= 1  # Should skip most stop words


class TestGraphRAG:
    def test_init_and_add(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            count = graph.add_document("doc_1", "Python is a language for Machine Learning")
            assert count > 0

    def test_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            graph.add_document("doc_1", "Python is used in Machine Learning")
            results = graph.search("Python")
            assert len(results) >= 1

    def test_search_no_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            results = graph.search("nonexistent_topic_xyz")
            assert results == []

    def test_get_related_concepts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            graph.add_document("doc_1", "Python and Machine Learning work well together")
            graph.add_document("doc_2", "Machine Learning uses Python extensively")
            related = graph.get_related_concepts("Python")
            assert len(related) >= 1

    def test_get_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            graph.add_document("doc_1", "Python for AI")
            graph.add_document("doc_2", "Java for Web")
            stats = graph.get_stats()
            assert stats["nodes"] > 0

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            graph.add_document("doc_1", "Python is great")
            cleared = graph.clear()
            assert cleared > 0
            assert graph.get_stats()["nodes"] == 0

    def test_add_text_batch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = GraphRAG(path=tmpdir)
            chunks = ["Python is for AI", "Java is for Web", "Rust is for Systems"]
            total = graph.add_text_batch("doc_batch", chunks)
            assert total > 0
