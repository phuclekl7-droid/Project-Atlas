"""
Hybrid Search Module (Feature 15)

Combines BM25 (keyword/sparse) search with Vector (dense) search
for more accurate document retrieval. Uses Reciprocal Rank Fusion (RRF)
to merge results from both methods.

Usage:
    hybrid = HybridSearch(
        vector_search_fn=knowledge_base.search,  # ChromaDB search
        index_name="atlas_knowledge",
    )
    results = hybrid.search("What is Python?", top_k=5)
"""

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from src.core import setup_logger

logger = setup_logger("hybrid_search")


# ============================================================
# BM25 Implementation (Sparse Search)
# ============================================================


class BM25Index:
    """Simple in-memory BM25 index for keyword search.

    BM25 is a bag-of-words retrieval function that ranks documents
    based on term frequency and inverse document frequency.

    Usage:
        index = BM25Index()
        index.add_document("doc1", "Python is a programming language")
        index.add_document("doc2", "JavaScript is for web development")
        results = index.search("programming language")
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 index.

        Args:
            k1: Term frequency saturation parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)
        """
        self._k1 = k1
        self._b = b
        self._documents: dict[str, str] = {}
        self._doc_terms: dict[str, Counter] = {}
        self._doc_lengths: dict[str, int] = {}
        self._total_docs = 0
        self._avg_doc_length = 0.0
        self._idf_cache: dict[str, float] = {}
        self._built = False

    def add_document(self, doc_id: str, text: str) -> None:
        """Add a document to the index.

        Args:
            doc_id: Unique document identifier
            text: Document text content
        """
        self._documents[doc_id] = text
        terms = self._tokenize(text)
        self._doc_terms[doc_id] = Counter(terms)
        self._doc_lengths[doc_id] = len(terms)
        self._built = False

    def add_documents(self, documents: list[tuple[str, str]]) -> None:
        """Add multiple documents at once.

        Args:
            documents: List of (doc_id, text) tuples
        """
        for doc_id, text in documents:
            self.add_document(doc_id, text)

    def build(self) -> None:
        """Build the index (compute IDF values, averages).

        Must be called after adding documents and before searching.
        """
        if self._built:
            return

        self._total_docs = len(self._documents)
        if self._total_docs == 0:
            self._built = True
            return

        # Calculate average document length
        total_length = sum(self._doc_lengths.values())
        self._avg_doc_length = total_length / self._total_docs

        # Calculate IDF for each term
        all_terms = set()
        for terms in self._doc_terms.values():
            all_terms.update(terms.keys())

        self._idf_cache = {}
        for term in all_terms:
            doc_count = sum(1 for t in self._doc_terms.values() if term in t)
            # BM25 IDF formula
            self._idf_cache[term] = math.log(
                (self._total_docs - doc_count + 0.5) / (doc_count + 0.5) + 1.0
            )

        self._built = True
        logger.debug(
            f"BM25 index built: {self._total_docs} docs, "
            f"{len(self._idf_cache)} unique terms, "
            f"avg length={self._avg_doc_length:.1f}"
        )

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float]]:
        """Search the index using BM25 scoring.

        Args:
            query: Search query string
            top_k: Number of top results to return

        Returns:
            List of (doc_id, score) tuples sorted by score descending
        """
        if not self._built:
            self.build()

        if self._total_docs == 0:
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # Count query terms
        query_term_counts = Counter(query_terms)

        # Compute BM25 score for each document
        scores: list[tuple[str, float]] = []
        for doc_id in self._documents:
            score = self._compute_bm25(doc_id, query_term_counts)
            if score > 0:
                scores.append((doc_id, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def clear(self) -> None:
        """Clear all documents from the index."""
        self._documents.clear()
        self._doc_terms.clear()
        self._doc_lengths.clear()
        self._idf_cache.clear()
        self._total_docs = 0
        self._avg_doc_length = 0.0
        self._built = False

    @property
    def document_count(self) -> int:
        """Number of indexed documents."""
        return self._total_docs

    # ── Internal ──

    def _compute_bm25(self, doc_id: str, query_terms: Counter) -> float:
        """Compute BM25 score for a single document.

        Args:
            doc_id: Document ID
            query_terms: Counter of query term frequencies

        Returns:
            BM25 score
        """
        doc_terms = self._doc_terms[doc_id]
        doc_length = self._doc_lengths[doc_id]
        score = 0.0

        for term, qty in query_terms.items():
            if term not in self._idf_cache:
                continue

            tf = doc_terms.get(term, 0)
            if tf == 0:
                continue

            idf = self._idf_cache[term]

            # BM25 formula
            numerator = tf * (self._k1 + 1)
            denominator = tf + self._k1 * (
                1 - self._b + self._b * (doc_length / self._avg_doc_length)
            )
            score += idf * (numerator / denominator) * qty

        return score

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text into lowercase terms.

        Strips punctuation, splits on whitespace, and
        filters out very short (<2 chars) tokens.
        """
        text = text.lower()
        # Remove punctuation and split
        terms = re.findall(r"\b[a-z0-9]+\b", text)
        # Filter very short tokens
        return [t for t in terms if len(t) >= 2]


# ============================================================
# Hybrid Search
# ============================================================


@dataclass
class HybridResult:
    """Single search result from hybrid search.

    Attributes:
        doc_id: Document identifier
        content: Document text content
        score: Combined score from RRF fusion
        bm25_score: Raw BM25 score (0 if not found by BM25)
        vector_score: Raw vector similarity score (0 if not found by vector)
        rank_bm25: Rank position in BM25 results
        rank_vector: Rank position in vector results
    """

    doc_id: str
    content: str
    score: float = 0.0
    bm25_score: float = 0.0
    vector_score: float = 0.0
    rank_bm25: int = 0
    rank_vector: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class HybridSearch:
    """Combines BM25 sparse search with vector dense search.

    Uses Reciprocal Rank Fusion (RRF) to merge results:
      RRF(d) = 1 / (k + rank_bm25(d)) + 1 / (k + rank_vector(d))

    This gives higher weight to documents that rank well in BOTH methods.

    Usage:
        hybrid = HybridSearch(vector_search_fn=kb.search)
        hybrid.add_documents(all_docs)
        results = hybrid.search("Python programming", top_k=5)
    """

    def __init__(
        self,
        vector_search_fn: Optional[Callable] = None,
        rrf_constant: int = 60,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
    ):
        """Initialize hybrid search.

        Args:
            vector_search_fn: Callable that takes a query string and
                            returns list of dicts with 'id', 'content', 'score'
            rrf_constant: RRF constant (default: 60)
            bm25_weight: Weight for BM25 in final score (0.0–1.0)
            vector_weight: Weight for vector in final score (0.0–1.0)
        """
        self._bm25 = BM25Index()
        self._vector_fn = vector_search_fn
        self._rrf_k = rrf_constant
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight
        self._storage: dict[str, str] = {}  # doc_id -> content

    def add_documents(
        self,
        documents: list[dict],
        id_field: str = "id",
        content_field: str = "content",
    ) -> int:
        """Add documents to both the BM25 index and storage.

        Args:
            documents: List of dicts with id and content fields
            id_field: Key for document ID
            content_field: Key for document text content

        Returns:
            Number of documents added
        """
        count = 0
        for doc in documents:
            doc_id = doc.get(id_field, str(hash(doc.get(content_field, ""))))
            content = doc.get(content_field, "")
            if content:
                self._storage[doc_id] = content
                self._bm25.add_document(doc_id, content)
                count += 1

        self._bm25.build()
        logger.debug(f"HybridSearch: added {count} documents (total: {len(self._storage)})")
        return count

    def search(
        self,
        query: str,
        top_k: int = 5,
        vector_top_k: int = 20,
    ) -> list[HybridResult]:
        """Perform hybrid search combining BM25 and vector results.

        Args:
            query: Search query
            top_k: Number of final results to return
            vector_top_k: Number of vector results to consider for fusion

        Returns:
            List of HybridResult objects sorted by combined score
        """
        if not query or not query.strip():
            return []

        # Step 1: BM25 search
        bm25_results = self._bm25.search(query, top_k=top_k * 2)
        bm25_scores = dict(bm25_results)
        bm25_ranks = {doc_id: i + 1 for i, (doc_id, _) in enumerate(bm25_results)}

        # Step 2: Vector search (if function provided)
        vector_scores: dict[str, float] = {}
        vector_ranks: dict[str, int] = {}

        if self._vector_fn:
            try:
                vector_results = self._vector_fn(query, n_results=vector_top_k)
                for i, result in enumerate(vector_results):
                    doc_id = getattr(result, 'id', None) or getattr(result, 'doc_id', None) or str(i)
                    score = getattr(result, 'score', 0.0) or getattr(result, 'similarity', 0.0)
                    if isinstance(score, (int, float)):
                        vector_scores[doc_id] = float(score)
                    vector_ranks[doc_id] = i + 1
                    # Ensure doc is in storage
                    content = getattr(result, 'content', '') or getattr(result, 'text', '')
                    if content and doc_id not in self._storage:
                        self._storage[doc_id] = content
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # Step 3: RRF fusion
        all_doc_ids = set(bm25_scores.keys()) | set(vector_scores.keys())
        fused_results = []

        for doc_id in all_doc_ids:
            rank_bm25 = bm25_ranks.get(doc_id, 999)
            rank_vector = vector_ranks.get(doc_id, 999)

            # RRF score
            rrf_bm25 = 1.0 / (self._rrf_k + rank_bm25)
            rrf_vector = 1.0 / (self._rrf_k + rank_vector)

            # Weighted combination
            combined_score = (
                self._bm25_weight * rrf_bm25
                + self._vector_weight * rrf_vector
            )

            fused_results.append(HybridResult(
                doc_id=doc_id,
                content=self._storage.get(doc_id, ""),
                score=round(combined_score, 4),
                bm25_score=round(bm25_scores.get(doc_id, 0.0), 4),
                vector_score=round(vector_scores.get(doc_id, 0.0), 4),
                rank_bm25=rank_bm25 if rank_bm25 < 999 else 0,
                rank_vector=rank_vector if rank_vector < 999 else 0,
            ))

        # Sort by combined score descending
        fused_results.sort(key=lambda r: r.score, reverse=True)
        return fused_results[:top_k]

    def get_stats(self) -> dict:
        """Get search index statistics."""
        return {
            "total_documents": len(self._storage),
            "bm25_documents": self._bm25.document_count,
            "bm25_terms": len(self._bm25._idf_cache) if hasattr(self._bm25, '_idf_cache') else 0,
            "vector_enabled": self._vector_fn is not None,
            "rrf_constant": self._rrf_k,
            "bm25_weight": self._bm25_weight,
            "vector_weight": self._vector_weight,
        }
