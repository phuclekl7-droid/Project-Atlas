"""Tests for Time-decay Memory Filter (Feature 18)."""

import time
import pytest
from src.core.time_decay import TimeDecayFilter, DecayResult


class TestTimeDecay:
    """Test time decay function."""

    def test_exponential_decay(self):
        tf = TimeDecayFilter(method="exponential", half_life_hours=24)
        # Fresh item (0 hours old) should retain full score
        result = tf.apply(1.0, hours_old=0)
        assert result.decayed_score == 1.0
        assert result.decay_factor == 1.0

    def test_exponential_halflife(self):
        tf = TimeDecayFilter(method="exponential", half_life_hours=24)
        # At exactly 24 hours, score should be ~50%
        result = tf.apply(1.0, hours_old=24)
        assert 0.45 <= result.decayed_score <= 0.55

    def test_linear_decay(self):
        tf = TimeDecayFilter(method="linear", half_life_hours=24)
        # At 12 hours, should be at 50%
        result = tf.apply(1.0, hours_old=12)
        assert result.decayed_score == 0.5

    def test_linear_past_halflife(self):
        tf = TimeDecayFilter(method="linear", half_life_hours=24)
        result = tf.apply(1.0, hours_old=48)
        assert result.decayed_score == 0.0

    def test_step_decay_before_threshold(self):
        tf = TimeDecayFilter(method="step", threshold_hours=24)
        result = tf.apply(0.8, hours_old=12)
        assert result.decayed_score == 0.8

    def test_step_decay_after_threshold(self):
        tf = TimeDecayFilter(method="step", threshold_hours=24)
        result = tf.apply(0.8, hours_old=36)
        assert result.decayed_score == 0.0

    def test_zero_score_stays_zero(self):
        tf = TimeDecayFilter()
        result = tf.apply(0.0, hours_old=100)
        assert result.decayed_score == 0.0

    def test_invalid_method(self):
        with pytest.raises(ValueError):
            TimeDecayFilter(method="invalid")

    def test_decay_result_attributes(self):
        tf = TimeDecayFilter(method="exponential")
        result = tf.apply(0.9, hours_old=6)
        assert isinstance(result, DecayResult)
        assert result.original_score == 0.9
        assert result.method == "exponential"
        assert result.retained_pct > 0


class TestBatchDecay:
    """Test batch decay application."""

    def test_batch_returns_correct_count(self):
        tf = TimeDecayFilter()
        now = time.time()
        items = [
            {"score": 0.9, "timestamp": now - 3600},    # 1 hour old
            {"score": 0.7, "timestamp": now - 86400},   # 24 hours old
        ]
        results = tf.apply_batch(items)
        assert len(results) == 2

    def test_batch_items_decayed(self):
        tf = TimeDecayFilter(method="linear", half_life_hours=24)
        now = time.time()
        items = [
            {"score": 1.0, "timestamp": now - 86400},  # 24h old, should be ~0
        ]
        results = tf.apply_batch(items)
        assert results[0].decayed_score < 0.1


class TestTimeDecayStats:
    def test_initial_stats(self):
        tf = TimeDecayFilter()
        stats = tf.get_stats()
        assert stats["total_applied"] == 0
        assert stats["method"] == "exponential"

    def test_stats_after_apply(self):
        tf = TimeDecayFilter()
        tf.apply(0.8, hours_old=1)
        assert tf.get_stats()["total_applied"] == 1
