"""Tests for PromptCompressor module (Feature 6)."""

import pytest
from src.core.prompt_compressor import PromptCompressor, CompressionResult


@pytest.fixture
def compressor():
    return PromptCompressor(min_savings=0)


class TestBasicCompression:
    """Test basic compression functionality."""

    def test_short_prompt_unchanged(self, compressor):
        """Short prompts should not be compressed."""
        result = compressor.compress("Hello")
        assert result.compressed == "Hello"
        assert result.savings_pct == 0.0

    def test_whitespace_normalization(self, compressor):
        """Excessive whitespace should be normalized."""
        result = compressor.compress("Hello    World\n\nHow are you?")
        assert "  " not in result.compressed
        assert "\n" not in result.compressed

    def test_filler_removal(self, compressor):
        """Common filler words should be removed."""
        result = compressor.compress("The quick brown fox jumps over the lazy dog")
        # "the" should be removed
        assert "the" not in result.compressed.lower() or result.compressed == "quick brown fox jumps over lazy dog"

    def test_phrase_replacement(self, compressor):
        """Verbose phrases should be replaced."""
        result = compressor.compress("Could you please help me with this?")
        assert "could you please" not in result.compressed.lower()

    def test_result_structure(self, compressor):
        """CompressionResult should have all fields."""
        result = compressor.compress("This is a test prompt that is long enough to compress")
        assert isinstance(result, CompressionResult)
        assert len(result.original) > 0
        assert len(result.compressed) > 0
        assert result.original_tokens > 0
        assert isinstance(result.strategies_applied, list)


class TestCompressionLevels:
    """Test different compression levels."""

    def test_light_level(self):
        """Light level should only normalize whitespace."""
        comp = PromptCompressor(min_savings=0, compression_level="light")
        result = comp.compress("Could you please tell me what is Python?")
        assert "whitespace_normalization" in result.strategies_applied
        assert "phrase_replacement" not in result.strategies_applied

    def test_balanced_level(self):
        """Balanced level should include deduplication."""
        comp = PromptCompressor(min_savings=0, compression_level="balanced")
        result = comp.compress("What is Python? Can you tell me about Python?")
        assert "deduplication" in result.strategies_applied

    def test_aggressive_level(self):
        """Aggressive level should include redundant question removal."""
        comp = PromptCompressor(min_savings=0, compression_level="aggressive")
        result = comp.compress("What is Python? What is Python programming language?")
        assert "redundant_question_removal" in result.strategies_applied


class TestDeduplication:
    """Test sentence deduplication."""

    def test_identical_sentences_deduped(self, compressor):
        """Identical sentences should be removed."""
        text = "Python is great. Python is great. I love Python."
        result = compressor.compress(text)
        assert result.compressed.count("Python is great") <= 1

    def test_unique_sentences_kept(self, compressor):
        """Different sentences should not be removed."""
        text = "Python is great. Java is also good. Rust is fast."
        result = compressor.compress(text)
        # Each sentence is different, should keep all
        assert "Python" in result.compressed
        assert "Java" in result.compressed
        assert "Rust" in result.compressed


class TestStats:
    """Test compression statistics."""

    def test_stats_update(self, compressor):
        """Compression stats should be updated after calls."""
        initial_stats = compressor.get_stats()
        compressor.compress("This is a test prompt for compression statistics")
        updated_stats = compressor.get_stats()
        assert updated_stats["total_compressed"] > initial_stats["total_compressed"]

    def test_compression_savings(self, compressor):
        """Compression should save tokens on verbose prompts."""
        verbose = "Could you please tell me what is the meaning of life in your opinion?"
        result = compressor.compress(verbose)
        assert result.savings_pct > 0

    def test_vietnamese_compression(self, compressor):
        """Vietnamese text should also be compressible."""
        text = "Cho tôi hỏi làm ơn cho tôi biết Python là gì?"
        result = compressor.compress(text)
        # Vietnamese stopwords like "cho", "tôi" may be removed
        assert len(result.compressed) <= len(result.original)
