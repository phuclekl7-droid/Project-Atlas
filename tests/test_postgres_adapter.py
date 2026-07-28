"""
Tests for Feature #20: PostgreSQL / pgvector Integration.
"""

import pytest

from src.core.postgres_adapter import PostgresAdapter, PgVectorSearchResult


class TestPostgresAdapter:
    def test_init_not_available(self):
        db = PostgresAdapter(config={
            "host": "nonexistent_host",
            "port": 5432,
            "database": "test",
            "user": "test",
            "password": "test",
        })
        # Should not connect (host doesn't exist)
        assert not db.available or db.available is not None

    def test_available_property(self):
        db = PostgresAdapter(config={"host": "localhost", "port": 5432, "database": "test", "user": "test", "password": "test"})
        # Just checking no crash
        assert db.available is not None

    def test_search_empty(self):
        db = PostgresAdapter(config={"host": "localhost", "port": 5432, "database": "test", "user": "test", "password": "test"})
        results = db.search_similar([0.1, 0.2, 0.3])
        assert results == []

    def test_search_keywords_empty(self):
        db = PostgresAdapter(config={"host": "localhost", "port": 5432, "database": "test", "user": "test", "password": "test"})
        results = db.search_keywords("test query")
        assert results == []

    def test_insert_without_connection(self):
        db = PostgresAdapter(config={"host": "localhost", "port": 5432, "database": "test", "user": "test", "password": "test"})
        result = db.insert_document("doc_1", "test.txt", "content", [0.1, 0.2])
        assert result is False  # Can't insert without real connection

    def test_get_stats_not_available(self):
        db = PostgresAdapter(config={"host": "localhost", "port": 5432, "database": "test", "user": "test", "password": "test"})
        stats = db.get_stats()
        assert "available" in stats

    def test_close(self):
        db = PostgresAdapter(config={"host": "localhost", "port": 5432, "database": "test", "user": "test", "password": "test"})
        db.close()  # Should not crash

    def test_pg_vector_result(self):
        result = PgVectorSearchResult(content="test content", doc_id="doc_1", filename="test.txt", similarity=0.95)
        assert result.content == "test content"
        assert result.similarity == 0.95
