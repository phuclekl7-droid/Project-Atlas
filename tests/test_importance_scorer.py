"""Tests for Memory Importance Scorer (Feature 14)."""

import pytest
from src.core.importance_scorer import ImportanceScorer, ScoreFactors


@pytest.fixture
def scorer():
    return ImportanceScorer()


class TestImportanceScoring:
    """Test message importance scoring."""

    def test_empty_message(self, scorer):
        score = scorer.score_message("")
        assert score == 0.0

    def test_short_greeting_low_score(self, scorer):
        score = scorer.score_message("Hello", role="user")
        assert score < 0.5

    def test_question_medium_score(self, scorer):
        score = scorer.score_message("What is the capital of France?", role="user")
        assert score > 0.3

    def test_code_block_high_score(self, scorer):
        score = scorer.score_message(
            "Here's the solution:\n```python\nprint('hello')\n```",
            role="assistant",
        )
        assert score > 0.3

    def test_email_entity_detected(self, scorer):
        score = scorer.score_message(
            "My email is john@example.com",
            role="user",
        )
        assert score > 0.3

    def test_multi_entity_boost(self, scorer):
        """Multiple entities should boost score."""
        score = scorer.score_message(
            "Email: user@test.com, URL: https://example.com, IP: 192.168.1.1",
            role="user",
        )
        assert score > 0.3

    def test_role_factor_user_vs_assistant(self, scorer):
        user_score = scorer.score_message("What is Python?", role="user")
        asst_score = scorer.score_message("What is Python?", role="assistant")
        assert user_score >= asst_score


class TestScoreFactors:
    """Test individual scoring factors."""

    def test_length_factor_increases_with_length(self, scorer):
        short = scorer._compute_factors("Hi", "user")
        long = scorer._compute_factors("A" * 500, "user")
        assert long.length_factor > short.length_factor

    def test_question_factor_present(self, scorer):
        factors = scorer._compute_factors("What is this?", "user")
        assert factors.question_factor > 0

    def test_code_factor_present(self, scorer):
        factors = scorer._compute_factors("Code: ```python\nx = 1\n```", "assistant")
        assert factors.code_factor > 0

    def test_weighted_score(self):
        factors = ScoreFactors(
            length_factor=0.5,
            question_factor=0.8,
            code_factor=0.0,
            entity_factor=0.0,
            term_factor=0.0,
            role_factor=0.6,
        )
        score = factors.weighted_score
        assert 0 < score < 1.0


class TestScoredMessages:
    """Test batch scoring and top-k selection."""

    def test_top_k_returns_correct_count(self, scorer):
        messages = [
            ("user", "Hi"),
            ("user", "What is Python?"),
            ("assistant", "Python is a language"),
        ]
        top = scorer.get_scored_messages(messages, top_k=2)
        assert len(top) == 2

    def test_top_k_sorted_by_score(self, scorer):
        messages = [
            ("user", "Hi"),
            ("user", "My email is user@test.com, call me at 555-0100"),
        ]
        top = scorer.get_scored_messages(messages, top_k=2)
        # The more detailed message should score higher
        assert top[0][2] >= top[1][2]

    def test_get_stats(self, scorer):
        assert scorer.get_stats()["total_scored"] == 0
        scorer.score_message("Test message")
        assert scorer.get_stats()["total_scored"] > 0
