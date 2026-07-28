"""
Unit tests for SpeedTracker (Tokens/sec Counter).

Tests:
- Initial state (no data)
- start() resets state properly
- record_tokens increments correctly
- stop() freezes elapsed time
- tokens_per_second calculation
- get_stats() returns correct dict
- get_badge_html() returns proper HTML
- reset() clears all state
- edge cases: zero tokens, zero time, rapid recording
"""

import time

import pytest

from src.features.speed_tracker import SpeedTracker


class TestSpeedTracker:
    def test_initial_state(self):
        """New tracker should have zero values."""
        tracker = SpeedTracker()
        assert tracker.total_tokens == 0
        assert tracker.elapsed_seconds == 0.0
        assert tracker.tokens_per_second == 0.0
        assert tracker.get_badge_html() == ""

    def test_start_resets_state(self):
        """start() should reset token count and timer."""
        tracker = SpeedTracker()
        tracker._total_tokens = 100
        tracker._start_time = time.time() - 10
        tracker.start()
        assert tracker.total_tokens == 0
        assert tracker._start_time is not None

    def test_record_tokens_increments(self):
        """record_tokens() should increment counter."""
        tracker = SpeedTracker()
        tracker.start()
        tracker.record_tokens(10)
        assert tracker.total_tokens == 10
        tracker.record_tokens(5)
        assert tracker.total_tokens == 15

    def test_record_tokens_default(self):
        """record_tokens() default count should be 1."""
        tracker = SpeedTracker()
        tracker.start()
        tracker.record_tokens()
        assert tracker.total_tokens == 1

    def test_stop_freezes_time(self):
        """stop() should freeze elapsed_seconds."""
        tracker = SpeedTracker()
        tracker.start()
        time.sleep(0.05)
        tracker.record_tokens(100)
        tracker.stop()
        elapsed = tracker.elapsed_seconds
        assert 0.03 <= elapsed <= 0.5  # Allow for timing variance
        # After stop, elapsed should be stable
        time.sleep(0.05)
        assert tracker.elapsed_seconds == elapsed  # Not changed

    def test_tokens_per_second(self):
        """tokens_per_second should be tokens / elapsed."""
        tracker = SpeedTracker()
        tracker.start()
        tracker._start_time = time.time() - 2.0  # Pretend 2s passed
        tracker.record_tokens(100)
        tps = tracker.tokens_per_second
        assert 40 <= tps <= 60  # Should be ~50 t/s

    def test_tokens_per_second_zero_tokens(self):
        """Zero tokens should return 0.0."""
        tracker = SpeedTracker()
        tracker.start()
        assert tracker.tokens_per_second == 0.0

    def test_tokens_per_second_zero_time(self):
        """Zero elapsed time should return 0.0."""
        tracker = SpeedTracker()
        assert tracker.tokens_per_second == 0.0

    def test_get_stats(self):
        """get_stats() should return correct dict."""
        tracker = SpeedTracker()
        tracker.start()
        tracker._start_time = time.time() - 1.0
        tracker.record_tokens(50)
        tracker.stop()
        stats = tracker.get_stats()
        assert "tokens_per_sec" in stats
        assert stats["total_tokens"] == 50
        assert 0.5 <= stats["elapsed_seconds"] <= 3.0

    def test_get_badge_html(self):
        """get_badge_html() should return HTML with speed."""
        tracker = SpeedTracker()
        tracker.start()
        tracker._start_time = time.time() - 2.0
        tracker.record_tokens(80)
        tracker.stop()
        html = tracker.get_badge_html()
        assert "⏱️" in html
        assert "t/s" in html
        assert "style" in html
        assert "40" in html or "39" in html or "41" in html  # ~40 t/s

    def test_get_badge_html_no_data(self):
        """No data should return empty string."""
        tracker = SpeedTracker()
        assert tracker.get_badge_html() == ""

    def test_reset_clears_all(self):
        """reset() should clear all state."""
        tracker = SpeedTracker()
        tracker.start()
        tracker.record_tokens(50)
        tracker.stop()
        assert tracker.total_tokens > 0
        tracker.reset()
        assert tracker.total_tokens == 0
        assert tracker.elapsed_seconds == 0.0
        assert tracker.tokens_per_second == 0.0

    def test_fast_speed_badge_color(self):
        """Fast speed (>=20 t/s) should use green-ish color (#4ecdc4)."""
        tracker = SpeedTracker()
        tracker.start()
        tracker._start_time = time.time() - 0.5
        tracker.record_tokens(20)
        tracker.stop()
        html = tracker.get_badge_html()
        assert "#4ecdc4" in html

    def test_medium_speed_badge_color(self):
        """Medium speed (5-20 t/s) should use yellow (#ffd700)."""
        tracker = SpeedTracker()
        tracker.start()
        tracker._start_time = time.time() - 2.0
        tracker.record_tokens(20)
        tracker.stop()
        html = tracker.get_badge_html()
        assert "#ffd700" in html

    def test_slow_speed_badge_color(self):
        """Slow speed (<5 t/s) should use red (#ff6b6b)."""
        tracker = SpeedTracker()
        tracker.start()
        tracker._start_time = time.time() - 5.0
        tracker.record_tokens(10)
        tracker.stop()
        html = tracker.get_badge_html()
        assert "#ff6b6b" in html
