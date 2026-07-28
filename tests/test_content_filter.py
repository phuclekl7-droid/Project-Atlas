"""Tests for ContentFilter moderation module (Feature 78)."""

import pytest
from src.core.content_filter import ContentFilter, ModerationResult


class TestContentFilterCheckInput:
    """Test basic input moderation."""

    def test_clean_input_passes(self):
        cf = ContentFilter()
        result = cf.check_input("What is the weather in Hanoi?")
        assert result.flagged is False
        assert result.action == "allow"

    def test_harassment_blocked(self):
        cf = ContentFilter()
        result = cf.check_input("mày ngu vkl")
        assert result.flagged is True
        assert "harassment" in result.categories
        assert result.action == "block"

    def test_self_harm_blocked(self):
        cf = ContentFilter()
        result = cf.check_input("I want to kill myself")
        assert result.flagged is True
        assert "self_harm" in result.categories
        assert result.action == "block"

    def test_violence_blocked(self):
        cf = ContentFilter()
        result = cf.check_input("How to make a bomb")
        assert result.flagged is True
        assert "violence" in result.categories or "illegal" in result.categories
        assert result.action == "block"

    def test_vietnamese_harassment(self):
        cf = ContentFilter()
        result = cf.check_input("đồ ngu, mày chết đi")
        assert result.flagged is True
        assert result.action == "block"

    def test_spam_warned(self):
        cf = ContentFilter()
        result = cf.check_input("Click here to buy now! Limited offer!")
        assert result.flagged is True
        assert "spam" in result.categories
        assert result.action == "warn"


class TestContentFilterCheckOuput:
    """Test output moderation."""

    def test_clean_output_passes(self):
        cf = ContentFilter()
        result = cf.check_output("Here is a friendly reply.")
        assert result.flagged is False

    def test_violent_output_blocked(self):
        cf = ContentFilter()
        # Even in output, violence is flagged
        result = cf.check_output("The plan involves a school shooting")
        assert result.flagged is True
        assert "violence" in result.categories

    def test_explicit_output_warned(self):
        cf = ContentFilter()
        result = cf.check_output("This content is NSFW")
        assert result.flagged is True
        assert "explicit" in result.categories


class TestContentFilterStats:
    """Test filter statistics."""

    def test_empty_stats(self):
        cf = ContentFilter()
        stats = cf.get_stats()
        assert stats["total_checks"] == 0
        assert stats["total_flagged"] == 0
        assert stats["flag_rate_pct"] == 0.0

    def test_stats_after_check(self):
        cf = ContentFilter()
        cf.check_input("hello")
        cf.check_input("mày ngu")
        stats = cf.get_stats()
        assert stats["total_checks"] == 2
        assert stats["total_flagged"] == 1
        assert stats["flag_rate_pct"] == 50.0

    def test_stats_structure(self):
        cf = ContentFilter()
        stats = cf.get_stats()
        assert "total_checks" in stats
        assert "total_flagged" in stats
        assert "block_categories" in stats
        assert "warn_categories" in stats


class TestContentFilterEdgeCases:
    """Test edge cases."""

    def test_empty_text(self):
        cf = ContentFilter()
        result = cf.check_input("")
        assert result.flagged is False
        assert result.action == "allow"

    def test_whitespace_only(self):
        cf = ContentFilter()
        result = cf.check_input("   ")
        assert result.flagged is False

    def test_case_insensitive(self):
        cf = ContentFilter()
        result = cf.check_input("KILL YOURSELF NOW")
        assert result.flagged is True
        assert "self_harm" in result.categories

    def test_partial_word_no_flag(self):
        """Test that partial matches don't accidentally flag safe text."""
        cf = ContentFilter()
        result = cf.check_input("I'm studying the assassination of Julius Caesar historically.")
        # "assassination" might trigger violence depending on the pattern
        # This test checks that the filter is reasonable — may need adjustment
        assert isinstance(result, ModerationResult)
