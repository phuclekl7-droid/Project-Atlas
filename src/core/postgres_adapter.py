"""
PostgreSQL / pgvector Integration (Feature #20).
Provides a PostgreSQL adapter for memory and knowledge base storage.

Supports:
- PostgreSQL connection with SQLAlchemy
- pgvector extension for vector similarity search
- Auto-fallback to SQLite when Postgres is not available
- Schema migration for vector columns

Usage:
    db = PostgresAdapter(
        host="localhost",
        port=5432,
        database="atlas",
        user="postgres",
        password="secret",
    )
    db.connect()
    results = db.search_similar(embedding=[0.1, 0.2, ...])
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.core import setup_logger

logger = setup_logger("postgres_adapter")

# Optional PostgreSQL dependencies
try:
    import psycopg2
    import psycopg2.extras

    _HAS_PSYCOPG2 = True
except ImportError:
    _HAS_PSYCOPG2 = False

try:
    from sqlalchemy import (
        Column, String, Integer, Float, Text, DateTime, create_engine,
    )
    from sqlalchemy.orm import declarative_base, Session

    _HAS_SQLALCHEMY = True
    Base = declarative_base()
except ImportError:
    _HAS_SQLALCHEMY = False
    Base = object


# ── Configuration ──

def _get_pg_config() -> dict:
    """Get PostgreSQL connection config from environment variables."""
    return {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", "5432")),
        "database": os.environ.get("PGDATABASE", "atlas"),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
        "min_connections": int(os.environ.get("PG_MIN_CONN", "2")),
        "max_connections": int(os.environ.get("PG_MAX_CONN", "10")),
    }


@dataclass
class PgVectorSearchResult:
    """Result from a pgvector similarity search."""
    content: str = ""
    doc_id: str = ""
    filename: str = ""
    similarity: float = 0.0
    metadata: dict = field(default_factory=dict)


class PostgresAdapter:
    """
    PostgreSQL adapter with pgvector support for the Knowledge Base.

    Auto-detects PostgreSQL availability and falls back to
    a simulated interface if not configured.

    Usage:
        db = PostgresAdapter()
        if db.available:
            db.create_tables()
            results = db.search_similar(query_embedding, n_results=5)
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or _get_pg_config()
        self._engine = None
        self._session = None
        self._lock = threading.Lock()
        self._connected = False

        # Check if Postgres is available
        self._check_availability()

    def _check_availability(self):
        """Check if PostgreSQL is accessible."""
        if not _HAS_PSYCOPG2 and not _HAS_SQLALCHEMY:
            logger.info(
                "PostgreSQL not available. Install: pip install psycopg2-binary sqlalchemy"
            )
            return

        # Try connecting
        try:
            if _HAS_SQLALCHEMY:
                url = (
                    f"postgresql://{self.config['user']}:{self.config['password']}"
                    f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
                )
                self._engine = create_engine(url, pool_pre_ping=True)
                self._engine.connect()
                logger.info(f"Connected to PostgreSQL at {self.config['host']}")
                self._connected = True
            elif _HAS_PSYCOPG2:
                conn = psycopg2.connect(**self.config)
                conn.close()
                logger.info(f"Connected to PostgreSQL at {self.config['host']}")
                self._connected = True
        except Exception as e:
            logger.info(f"PostgreSQL not available: {e}")
            logger.info("Using SQLite fallback (default memory module)")

    @property
    def available(self) -> bool:
        """Whether PostgreSQL is connected and available."""
        return self._connected

    # ── Schema Management ──

    def create_tables(self) -> bool:
        """Create required tables and enable pgvector extension."""
        if not self._connected or not self._engine:
            return False

        try:
            with self._engine.connect() as conn:
                # Enable pgvector extension
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.commit()

                # Create documents table with vector support
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id SERIAL PRIMARY KEY,
                        doc_id VARCHAR(64) NOT NULL,
                        filename TEXT NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector(768),
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(doc_id, filename)
                    )
                """)
                conn.commit()

                # Create index for vector search
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_documents_embedding
                    ON documents USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """)
                conn.commit()

            logger.info("PostgreSQL tables created successfully")
            return True
        except Exception as e:
            logger.warning(f"Failed to create PostgreSQL tables: {e}")
            return False

    # ── Vector Operations ──

    def insert_document(
        self,
        doc_id: str,
        filename: str,
        content: str,
        embedding: Optional[list[float]] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Insert a document with its embedding vector."""
        if not self._connected or not self._engine:
            return False

        try:
            with self._engine.connect() as conn:
                stmt = """
                    INSERT INTO documents (doc_id, filename, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s::vector, %s::jsonb)
                    ON CONFLICT (doc_id, filename) DO UPDATE
                    SET content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata
                """
                vec_str = json.dumps(embedding) if embedding else None
                conn.execute(
                    stmt,
                    (
                        doc_id,
                        filename,
                        content[:50000],
                        vec_str,
                        json.dumps(metadata or {}),
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.warning(f"Failed to insert document: {e}")
            return False

    def search_similar(
        self,
        embedding: list[float],
        n_results: int = 5,
        similarity_threshold: float = 0.7,
    ) -> list[PgVectorSearchResult]:
        """
        Search for similar documents using cosine similarity.

        Requires pgvector extension to be enabled.

        Args:
            embedding: Query embedding vector
            n_results: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of PgVectorSearchResult objects
        """
        if not self._connected or not self._engine:
            return []

        try:
            vec_str = json.dumps(embedding)
            with self._engine.connect() as conn:
                results = conn.execute(
                    """
                    SELECT content, doc_id, filename,
                           1 - (embedding <=> %s::vector) AS similarity,
                           metadata
                    FROM documents
                    WHERE embedding IS NOT NULL
                      AND 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY similarity DESC
                    LIMIT %s
                    """,
                    (vec_str, vec_str, similarity_threshold, n_results),
                ).fetchall()

                return [
                    PgVectorSearchResult(
                        content=row[0],
                        doc_id=row[1],
                        filename=row[2],
                        similarity=float(row[3]),
                        metadata=row[4] or {},
                    )
                    for row in results
                ]
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def search_keywords(
        self,
        query: str,
        n_results: int = 10,
    ) -> list[PgVectorSearchResult]:
        """Search documents by keyword (PostgreSQL full-text search)."""
        if not self._connected or not self._engine:
            return []

        try:
            with self._engine.connect() as conn:
                results = conn.execute(
                    """
                    SELECT content, doc_id, filename,
                           ts_rank(to_tsvector('english', content),
                                   plainto_tsquery('english', %s)) AS rank,
                           metadata
                    FROM documents
                    WHERE to_tsvector('english', content) @@
                          plainto_tsquery('english', %s)
                    ORDER BY rank DESC
                    LIMIT %s
                    """,
                    (query, query, n_results),
                ).fetchall()

                return [
                    PgVectorSearchResult(
                        content=row[0],
                        doc_id=row[1],
                        filename=row[2],
                        similarity=float(row[3]),
                        metadata=row[4] or {},
                    )
                    for row in results
                ]
        except Exception as e:
            logger.warning(f"Keyword search failed: {e}")
            return []

    def get_stats(self) -> dict:
        """Get database statistics."""
        if not self._connected:
            return {"available": False}

        try:
            with self._engine.connect() as conn:
                doc_count = conn.execute(
                    "SELECT COUNT(*) FROM documents"
                ).scalar()
                return {
                    "available": True,
                    "documents": doc_count,
                    "host": self.config["host"],
                    "database": self.config["database"],
                }
        except Exception:
            return {"available": False}

    def close(self):
        """Close the database connection."""
        if self._engine:
            self._engine.dispose()
            self._connected = False
            logger.info("PostgreSQL connection closed")
