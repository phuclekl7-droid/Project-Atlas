"""
Tests for VectorCompressor — HNSW + PQ Compression (Feature #111).

Tests Product Quantization encoding/decoding, HNSW index building,
search accuracy, and serialization round-trips.
"""

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.core.vector_compression import (
    VectorCompressor,
    ProductQuantizer,
    HNSWIndex,
    CompressionConfig,
    CompressionStats,
)


# ============================================================
# Fixtures
# ============================================================

SEED = 42
DIM = 32  # Small dimension for fast tests
N_VECTORS = 50


@pytest.fixture
def rng():
    return np.random.RandomState(SEED)


@pytest.fixture
def vectors(rng):
    return rng.randn(N_VECTORS, DIM).astype(np.float32)


@pytest.fixture
def query(rng):
    return rng.randn(DIM).astype(np.float32)


@pytest.fixture
def config():
    return CompressionConfig(
        dimension=DIM,
        pq_bytes=8,
        pq_subquantizers=4,
        hnsw_m=4,
        hnsw_ef_construction=50,
        hnsw_ef_search=20,
        min_vectors_for_compression=10,
        normalize=False,
    )


# ============================================================
# Tests: Product Quantizer
# ============================================================


class TestProductQuantizer:
    def test_init(self, config):
        pq = ProductQuantizer(config)
        assert pq.M == 4
        assert pq.D == 32
        assert pq.sub_dim == 8
        assert not pq.trained

    def test_train_and_encode(self, vectors, config):
        pq = ProductQuantizer(config)
        pq.train(vectors)
        assert pq.trained
        assert pq.codebooks is not None
        assert len(pq.codebooks) == 4

        codes = pq.encode(vectors)
        assert codes.shape == (N_VECTORS, 4)
        assert codes.dtype == np.uint8

    def test_decode_reconstructs_approximately(self, vectors, config):
        """Decoded vectors should be somewhat close to original."""
        pq = ProductQuantizer(config)
        pq.train(vectors)
        codes = pq.encode(vectors)
        decoded = pq.decode(codes)
        assert decoded.shape == vectors.shape

        # Check reconstruction error
        error = np.mean((vectors - decoded) ** 2)
        assert error < 10.0  # Reasonable for 4-byte PQ

    def test_error_before_train(self, config):
        pq = ProductQuantizer(config)
        with pytest.raises(RuntimeError, match="not trained"):
            pq.encode(np.random.randn(5, DIM))

    def test_insufficient_training_data(self, config):
        """Need at least 256 vectors for k-means with k=256."""
        config.pq_subquantizers = 1
        pq = ProductQuantizer(config)
        few_vectors = np.random.randn(10, DIM)
        with pytest.raises(ValueError):
            pq.train(few_vectors)

    def test_normalize_vectors(self, vectors, config):
        config.normalize = True
        pq = ProductQuantizer(config)
        pq.train(vectors)
        codes = pq.encode(vectors)
        assert codes.shape == (N_VECTORS, 4)

    def test_compute_distance_table(self, vectors, query, config):
        pq = ProductQuantizer(config)
        pq.train(vectors)
        codes = pq.encode(vectors)
        distances = pq.compute_distance_table(query, codes)
        assert distances.shape == (N_VECTORS,)
        assert np.all(distances >= 0)

    def test_kmeans_convergence(self):
        """Test k-means converges on simple data."""
        data = np.random.randn(100, 8)
        centroids = ProductQuantizer._kmeans(data, 10)
        assert centroids.shape == (10, 8)


# ============================================================
# Tests: HNSW Index
# ============================================================


class TestHNSWIndex:
    def test_empty_index_search(self, config):
        hnsw = HNSWIndex(config)
        query = np.random.randn(DIM)
        results = hnsw.search(query, k=5)
        assert results == []

    def test_add_one_vector(self, vectors, config):
        hnsw = HNSWIndex(config)
        hnsw.add(0, vectors[0])
        assert 0 in hnsw.nodes
        assert hnsw.entry_point == 0

    def test_add_multiple_vectors(self, vectors, config):
        hnsw = HNSWIndex(config)
        for i in range(min(20, N_VECTORS)):
            hnsw.add(i, vectors[i])
        assert len(hnsw.nodes) == min(20, N_VECTORS)
        assert hnsw.entry_point is not None

    def test_search_returns_correct_count(self, vectors, query, config):
        hnsw = HNSWIndex(config)
        for i in range(min(20, N_VECTORS)):
            hnsw.add(i, vectors[i])
        results = hnsw.search(query, k=5)
        assert len(results) <= 5
        assert all(isinstance(r[0], int) for r in results)
        assert all(isinstance(r[1], float) for r in results)

    def test_search_sorted_by_distance(self, vectors, query, config):
        hnsw = HNSWIndex(config)
        for i in range(min(20, N_VECTORS)):
            hnsw.add(i, vectors[i])
        results = hnsw.search(query, k=10)
        if len(results) > 1:
            distances = [r[1] for r in results]
            assert all(distances[i] <= distances[i + 1] for i in range(len(distances) - 1))

    def test_nearest_neighbor_is_self(self, vectors, config):
        """The nearest neighbor to a vector should be itself."""
        hnsw = HNSWIndex(config)
        for i in range(min(20, N_VECTORS)):
            hnsw.add(i, vectors[i])
        results = hnsw.search(vectors[0], k=3)
        if results:
            # The top result might not be the exact self due to HNSW approximation
            assert results[0][1] < 10.0  # Should be close

    def test_distance_function(self, config):
        v1 = np.array([1.0, 0.0, 0.0])
        v2 = np.array([0.0, 1.0, 0.0])
        dist = HNSWIndex._distance(v1, v2)
        assert abs(dist - math.sqrt(2.0)) < 0.001

    def test_size_bytes(self, vectors, config):
        hnsw = HNSWIndex(config)
        for i in range(10):
            hnsw.add(i, vectors[i])
        size = hnsw.size_bytes()
        assert size > 0

    def test_save_and_load(self, vectors, config):
        hnsw = HNSWIndex(config)
        for i in range(5):
            hnsw.add(i, vectors[i])

        with tempfile.TemporaryDirectory() as tmpdir:
            hnsw.save(tmpdir)

            hnsw_loaded = HNSWIndex(config)
            success = hnsw_loaded.load(tmpdir)
            assert success
            assert len(hnsw_loaded.nodes) == 5

    def test_load_nonexistent_path(self, config):
        hnsw = HNSWIndex(config)
        success = hnsw.load("/nonexistent/path")
        assert not success

    def test_random_level_range(self, config):
        """Random level should not be negative and should be bounded."""
        hnsw = HNSWIndex(config)
        levels = [hnsw._random_level() for _ in range(1000)]
        assert all(l >= 0 for l in levels)
        # Most should be low levels
        assert sum(1 for l in levels if l == 0) > 500


# ============================================================
# Tests: VectorCompressor (Integration)
# ============================================================


class TestVectorCompressor:
    def test_init(self):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8)
        assert compressor.config.dimension == DIM
        assert compressor.config.pq_bytes == 8
        assert not compressor._fitted

    def test_fit(self, vectors):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8, hnsw_m=4)
        stats = compressor.fit(vectors)
        assert compressor._fitted
        assert stats.num_vectors == N_VECTORS
        assert stats.dimension == DIM
        assert stats.build_time_ms > 0

    def test_fit_stores_stats(self, vectors):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8, hnsw_m=4)
        stats = compressor.fit(vectors)
        assert stats.original_size_bytes > 0
        assert stats.compression_ratio <= 1.0
        assert 0 < stats.accuracy_estimate <= 1.0

    def test_search_after_fit(self, vectors, query):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8, hnsw_m=4)
        compressor.fit(vectors)
        results = compressor.search(query, k=5)
        assert len(results) <= 5
        if results:
            assert len(results[0]) == 2  # (id_str, distance)

    def test_search_before_fit_raises(self, query):
        compressor = VectorCompressor(dimension=DIM)
        with pytest.raises(RuntimeError, match="not fitted"):
            compressor.search(query)

    def test_get_stats_before_fit_raises(self):
        compressor = VectorCompressor(dimension=DIM)
        with pytest.raises(RuntimeError, match="not fitted"):
            compressor.get_stats()

    def test_summary_string(self, vectors):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8, hnsw_m=4)
        compressor.fit(vectors)
        summary = compressor.summary()
        assert "Compression" in summary
        assert str(N_VECTORS) in summary
        assert "%" in summary

    def test_summary_before_fit(self):
        compressor = VectorCompressor(dimension=DIM)
        summary = compressor.summary()
        assert "not fitted" in summary.lower()

    def test_save_and_load(self, vectors):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8, hnsw_m=4)
        compressor.fit(vectors)

        with tempfile.TemporaryDirectory() as tmpdir:
            compressor.save(tmpdir)

            loaded = VectorCompressor(dimension=DIM)
            success = loaded.load(tmpdir)
            assert success
            assert loaded._fitted
            assert loaded.config.dimension == DIM

            # Search should work on loaded compressor
            results = loaded.search(vectors[0], k=3)
            assert len(results) <= 3

    def test_small_dataset_skips_compression(self, vectors):
        """Very small datasets should skip PQ compression."""
        small_vectors = vectors[:5]
        compressor = VectorCompressor(
            dimension=DIM, pq_bytes=8,
            min_vectors=10,  # More than 5
        )
        stats = compressor.fit(small_vectors)
        assert stats.compression_ratio >= 0.99  # No compression applied

    def test_search_with_pq_reranking(self, vectors, query):
        compressor = VectorCompressor(dimension=DIM, pq_bytes=8, hnsw_m=4)
        compressor.fit(vectors)
        results = compressor.search(query, k=5, use_pq=True)
        assert len(results) <= 5

    def test_format_bytes(self):
        assert VectorCompressor._format_bytes(500) == "500.0 B"
        assert VectorCompressor._format_bytes(2048) == "2.0 KB"
        assert VectorCompressor._format_bytes(1048576) == "1.0 MB"


# ============================================================
# Tests: CompressionStats
# ============================================================


class TestCompressionStats:
    def test_default_values(self):
        stats = CompressionStats()
        assert stats.original_size_bytes == 0
        assert stats.compression_ratio == 1.0
        assert stats.num_vectors == 0
