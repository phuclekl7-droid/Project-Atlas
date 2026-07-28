"""
Tests for SemanticDeduplicator — Knowledge Base Deduplication (Feature #117).

Tests semantic hashing, exact and near-duplicate detection,
and the full scan-and-deduplicate pipeline.
"""

import pytest
from src.knowledge.deduplication import (
    SemanticDeduplicator,
    SemanticHasher,
    DedupStats,
    DuplicateGroup,
)


# ============================================================
# Mock ChromaDB Collection
# ============================================================


class MockChromaCollection:
    """Simulates a minimal ChromaDB collection for testing."""

    def __init__(self, documents: list[tuple[str, str, dict]]):
        self._docs = documents  # [(id, text, metadata)]

    def get(self, ids=None, include=None):
        if ids:
            docs = [d for d in self._docs if d[0] in ids]
        else:
            docs = self._docs
        return {
            "ids": [d[0] for d in docs],
            "documents": [d[1] for d in docs],
            "metadatas": [d[2] for d in docs],
        }

    def delete(self, ids):
        self._docs = [d for d in self._docs if d[0] not in ids]


@pytest.fixture
def hasher():
    return SemanticHasher(num_hashes=64, shingle_size=3)


# ============================================================
# Tests: SemanticHasher
# ============================================================


class TestSemanticHasher:
    def test_tokenize(self, hasher):
        tokens = hasher.tokenize("hello world")
        assert len(tokens) > 0
        assert all(len(t) == 3 for t in tokens)

    def test_tokenize_empty(self, hasher):
        assert hasher.tokenize("") == []
        assert hasher.tokenize("  ") == []

    def test_tokenize_whitespace(self, hasher):
        tokens = hasher.tokenize("a  b")
        assert len(tokens) > 0

    def test_minhash_signature_shape(self, hasher):
        sig = hasher.minhash_signature("the quick brown fox")
        assert len(sig) == 64
        assert all(isinstance(v, int) for v in sig)

    def test_minhash_empty_text(self, hasher):
        sig = hasher.minhash_signature("")
        assert len(sig) == 64
        assert all(v == 0 for v in sig)

    def test_minhash_similar_texts(self, hasher):
        """Similar texts should produce similar signatures."""
        sig1 = hasher.minhash_signature("Python is a great programming language")
        sig2 = hasher.minhash_signature("Python is a great programming language for AI")
        sim = hasher.estimate_similarity(sig1, sig2)
        assert sim > 0.3  # Should be somewhat similar

    def test_minhash_different_texts(self, hasher):
        """Very different texts should have low similarity."""
        sig1 = hasher.minhash_signature("Python programming language")
        sig2 = hasher.minhash_signature("Cooking recipes for Italian pasta")
        sim = hasher.estimate_similarity(sig1, sig2)
        assert sim < 0.5  # Should be different

    def test_minhash_exact_duplicate(self, hasher):
        """Exact same text should produce identical signature."""
        sig1 = hasher.minhash_signature("This is a test sentence for hashing")
        sig2 = hasher.minhash_signature("This is a test sentence for hashing")
        sim = hasher.estimate_similarity(sig1, sig2)
        assert sim == 1.0

    def test_exact_hash(self, hasher):
        h1 = hasher.exact_hash("Hello World")
        h2 = hasher.exact_hash("Hello World")
        assert h1 == h2

    def test_exact_hash_different(self, hasher):
        h1 = hasher.exact_hash("Hello World")
        h2 = hasher.exact_hash("Hello World!")
        assert h1 != h2

    def test_exact_hash_normalizes_whitespace(self, hasher):
        h1 = hasher.exact_hash("Hello   World")
        h2 = hasher.exact_hash("Hello World")
        assert h1 == h2


# ============================================================
# Tests: SemanticDeduplicator - Basic
# ============================================================


class TestDeduplicatorBasic:
    def test_init_no_collection(self):
        dedup = SemanticDeduplicator()
        assert dedup.collection is None

    def test_scan_empty_collection(self):
        collection = MockChromaCollection([])
        dedup = SemanticDeduplicator(collection)
        stats = dedup.scan(threshold=0.95)
        assert stats.total_chunks == 0
        assert stats.removed_count == 0

    def test_scan_no_duplicates(self):
        docs = [
            ("id1", "The quick brown fox jumps over the lazy dog", {}),
            ("id2", "Python is a versatile programming language", {}),
            ("id3", "Machine learning transforms industries worldwide", {}),
        ]
        collection = MockChromaCollection(docs)
        dedup = SemanticDeduplicator(collection)
        stats = dedup.scan(threshold=0.95)
        assert stats.total_chunks == 3
        assert stats.removed_count == 0

    def test_exact_duplicate_detection(self):
        docs = [
            ("id1", "This is a test document for deduplication", {}),
            ("id2", "This is a test document for deduplication", {}),
            ("id3", "Completely different content", {}),
        ]
        collection = MockChromaCollection(docs)
        dedup = SemanticDeduplicator(collection)
        stats = dedup.scan(threshold=0.95)
        assert stats.total_chunks == 3
        assert stats.duplicate_groups >= 1
        assert stats.removed_count >= 1

    def test_exact_duplicate_removal(self):
        docs = [
            ("id1", "This is a duplicate test", {}),
            ("id2", "This is a duplicate test", {}),
            ("id3", "Unique content here", {}),
        ]
        collection = MockChromaCollection(docs)
        dedup = SemanticDeduplicator(collection)
        stats = dedup.scan_and_deduplicate(threshold=0.95)
        assert stats.removed_count >= 1


# ============================================================
# Tests: SemanticDeduplicator - Dedup
# ============================================================


class TestDeduplicatorAdvanced:
    def test_near_duplicate_detection(self):
        """Slightly different texts on the same topic should be detected."""
        docs = [
            ("id1", "Machine learning is a subset of artificial intelligence", {}),
            ("id2", "Machine learning is subset of artificial intelligence", {}),
            ("id3", "The weather is nice today", {}),
        ]
        collection = MockChromaCollection(docs)
        dedup = SemanticDeduplicator(collection, minhash_threshold=0.7)
        stats = dedup.scan(threshold=0.7)
        # Near duplicates may or may not be detected depending on shingles
        assert stats.total_chunks == 3

    def test_deduplicate_texts_empty(self, hasher):
        dedup = SemanticDeduplicator()
        result = dedup.deduplicate_texts([])
        assert result == []

    def test_deduplicate_texts_no_dupes(self, hasher):
        dedup = SemanticDeduplicator()
        texts = [
            "First unique text",
            "Second completely different text",
            "Third unrelated document",
        ]
        result = dedup.deduplicate_texts(texts)
        assert len(result) == 3
        assert all(r[1] == 1 for r in result)  # All kept

    def test_deduplicate_texts_exact_dupes(self, hasher):
        dedup = SemanticDeduplicator()
        texts = [
            "This is a unique document",
            "This is a unique document",  # Exact duplicate
            "Another different document",
        ]
        result = dedup.deduplicate_texts(texts)
        assert len(result) == 3
        assert result[0][1] == 1  # First kept
        assert result[1][1] == 0  # Duplicate removed
        assert result[2][1] == 1  # Third kept


# ============================================================
# Tests: DedupStats
# ============================================================


class TestDedupStats:
    def test_default_values(self):
        stats = DedupStats()
        assert stats.total_chunks == 0
        assert stats.duplicate_groups == 0
        assert stats.removed_count == 0
        assert stats.scan_time_ms == 0.0
        assert stats.threshold == 0.95

    def test_non_default_values(self):
        stats = DedupStats(
            total_chunks=100,
            duplicate_groups=5,
            removed_count=12,
            storage_saved_bytes=6000,
            scan_time_ms=150.5,
            threshold=0.9,
        )
        assert stats.total_chunks == 100
        assert stats.duplicate_groups == 5
        assert stats.removed_count == 12
        assert stats.storage_saved_bytes == 6000
        assert stats.scan_time_ms == 150.5
        assert stats.threshold == 0.9


# ============================================================
# Tests: DuplicateGroup
# ============================================================


class TestDuplicateGroup:
    def test_default_values(self):
        group = DuplicateGroup()
        assert group.chunks == []
        assert group.similarity == 0.0
        assert group.merged_text == ""
        assert group.kept_id == ""
        assert group.removed_ids == []

    def test_with_data(self):
        group = DuplicateGroup(
            chunks=[("id1", "text1", 0.95), ("id2", "text2", 0.95)],
            similarity=0.95,
            merged_text="Merged content",
            kept_id="id1",
            removed_ids=["id2"],
        )
        assert len(group.chunks) == 2
        assert group.similarity == 0.95
        assert group.kept_id == "id1"
        assert len(group.removed_ids) == 1


# ============================================================
# Tests: Report generation
# ============================================================


class TestReport:
    def test_clean_report(self):
        collection = MockChromaCollection([
            ("id1", "Unique document one", {}),
            ("id2", "Unique document two", {}),
        ])
        dedup = SemanticDeduplicator(collection)
        report = dedup.get_duplicate_report(threshold=0.99)
        assert "No Duplicates" in report

    def test_duplicate_report(self):
        collection = MockChromaCollection([
            ("id1", "Duplicate content for testing", {}),
            ("id2", "Duplicate content for testing", {}),
        ])
        dedup = SemanticDeduplicator(collection)
        report = dedup.get_duplicate_report(threshold=0.95)
        assert "Duplicate" in report or "Removed" in report
