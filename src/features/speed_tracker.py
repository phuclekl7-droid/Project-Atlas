"""
Speed Tracker (Feature: Tokens/sec Counter)

Measures response generation speed (tokens per second) and renders
a small badge on the UI showing real-time performance metrics.

Usage:
    tracker = SpeedTracker()
    tracker.start()
    # ... generate tokens ...
    tracker.record_tokens(num_tokens)
    badge_html = tracker.get_badge_html()  # "⏱️ 42.5 t/s (1.2s)"
"""

import time
from typing import Optional


class SpeedTracker:
    """
    Tracks token generation speed and renders a badge.

    Typical flow:
        tracker = SpeedTracker()
        tracker.start()
        for token in stream:
            tracker.record_tokens(1)
        badge = tracker.get_badge_html()

    Thread-safe for single-threaded Streamlit usage.
    """

    def __init__(self):
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._total_tokens: int = 0

    def start(self) -> None:
        """Start the timer. Resets any previous state."""
        self._start_time = time.time()
        self._end_time = None
        self._total_tokens = 0

    def record_tokens(self, count: int = 1) -> None:
        """
        Record that `count` tokens have been generated.

        Args:
            count: Number of tokens generated since last call (default 1)
        """
        self._total_tokens += count

    def stop(self) -> None:
        """Stop the timer. Freezes the elapsed time."""
        self._end_time = time.time()

    @property
    def elapsed_seconds(self) -> float:
        """Return elapsed time in seconds (up to current time if still running)."""
        if self._end_time is not None:
            return self._end_time - (self._start_time or self._end_time)
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    @property
    def tokens_per_second(self) -> float:
        """
        Return tokens per second based on current elapsed time.

        Returns 0.0 if no tokens or no time elapsed.
        """
        elapsed = self.elapsed_seconds
        if elapsed <= 0 or self._total_tokens <= 0:
            return 0.0
        return self._total_tokens / elapsed

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def get_stats(self) -> dict:
        """
        Return a dict with all metrics.

        Returns:
            dict with keys: tokens_per_sec, total_tokens, elapsed_seconds
        """
        return {
            "tokens_per_sec": round(self.tokens_per_second, 2),
            "total_tokens": self._total_tokens,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }

    def get_badge_html(self) -> str:
        """
        Render a small HTML badge showing generation speed.

        Example: "⏱️ 42.5 t/s (1.2s)"

        Returns:
            HTML string or empty string if no data.
        """
        if self._total_tokens <= 0 or self.elapsed_seconds <= 0:
            return ""

        tps = self.tokens_per_second
        elapsed = self.elapsed_seconds

        # Color the badge based on speed tier
        color = "#4ecdc4" if tps >= 20 else ("#ffd700" if tps >= 5 else "#ff6b6b")

        return (
            f'<span style="'
            f'display:inline-block;'
            f'padding:0.1rem 0.5rem;'
            f'border-radius:8px;'
            f'font-size:0.65rem;'
            f'font-weight:600;'
            f'background:{color}15;'
            f'color:{color};'
            f'border:1px solid {color}30;'
            f'margin-left:0.3rem;'
            f'white-space:nowrap;'
            f'">'
            f'⏱️ {tps:.1f} t/s ({elapsed:.1f}s)'
            f'</span>'
        )

    def reset(self) -> None:
        """Reset all state."""
        self._start_time = None
        self._end_time = None
        self._total_tokens = 0
