"""
Rate Limiter: Sliding-window rate limiter for API calls and token usage.

Supports two dimensions of rate limiting:
- Requests per time window (e.g., 60 requests/minute for OpenAI)
- Tokens per time window (e.g., 100,000 tokens/minute for GPT-4o-mini)

Provides both sync (blocking) and async (non-blocking) wait interfaces.

Usage:
    limiter = RateLimiter(max_requests=60, window_seconds=60)
    limiter.wait_if_needed()       # Blocks until under the limit
    await limiter.async_wait_if_needed()  # Non-blocking wait

    # With token tracking
    limiter = RateLimiter(max_requests=60, max_tokens=100000)
    limiter.wait_if_needed(tokens=500)  # Waits for both request + token budget
"""

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger

logger = setup_logger("rate_limiter")


@dataclass
class _RequestRecord:
    """A single request record with timestamp and token count."""

    timestamp: float
    tokens: int = 0


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded and wait is not possible."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None,
        limit_type: str = "requests",
    ):
        self.retry_after = retry_after
        self.limit_type = limit_type
        super().__init__(message)


class RateLimiter:
    """
    Sliding-window rate limiter for API calls and token usage.

    Thread-safe (RLock) for concurrent access.
    Supports both sync and async wait operations.

    Attributes:
        max_requests: Maximum requests allowed in the window
        max_tokens: Maximum tokens allowed in the window (0 = unlimited)
        window_seconds: Time window in seconds
    """

    def __init__(
        self,
        max_requests: int = 60,
        max_tokens: int = 0,
        window_seconds: int = 60,
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Max requests in the time window (0 = unlimited)
            max_tokens: Max tokens in the time window (0 = unlimited)
            window_seconds: Sliding window duration in seconds
        """
        self.max_requests = max_requests
        self.max_tokens = max_tokens
        self.window_seconds = window_seconds

        self._records: deque[_RequestRecord] = deque()
        self._lock = threading.RLock()
        self._total_requests_blocked = 0
        self._total_tokens_used = 0
        self._rate_limited_count = 0

        if max_requests > 0:
            logger.debug(
                f"RateLimiter initialized: {max_requests} req / {window_seconds}s"
                + (f", {max_tokens} tokens / {window_seconds}s" if max_tokens > 0 else "")
            )

    # ── Public API ──

    def check(self, tokens: int = 0) -> bool:
        """
        Check if a request with the given token count can proceed.

        Returns True if allowed, False if rate limited.
        Does NOT record the request (use `record()` for that).
        """
        self._cleanup()

        if self.max_requests > 0 and len(self._records) >= self.max_requests:
            self._rate_limited_count += 1
            return False

        if self.max_tokens > 0:
            current_tokens = sum(r.tokens for r in self._records)
            if current_tokens + tokens > self.max_tokens:
                self._rate_limited_count += 1
                return False

        return True

    def record(self, tokens: int = 0) -> None:
        """
        Record a request in the sliding window.

        Must be called AFTER the request is made.
        """
        with self._lock:
            now = time.time()
            self._records.append(_RequestRecord(timestamp=now, tokens=tokens))
            self._total_tokens_used += tokens

    def wait_if_needed(self, tokens: int = 0) -> float:
        """
        Block until a request can proceed, then record it.

        Returns the wait time in seconds (0 if no wait needed).

        Raises:
            RateLimitExceeded: If the limit cannot be satisfied within the window
        """
        # Clean up expired records first
        self._cleanup()

        # Fast path: no waiting needed
        if self.check(tokens):
            self.record(tokens)
            return 0.0

        # Calculate wait time
        wait_time = self._calculate_wait_time(tokens)
        if wait_time <= 0:
            self.record(tokens)
            return 0.0

        logger.debug(f"Rate limit: waiting {wait_time:.1f}s (tokens={tokens})")
        self._total_requests_blocked += 1

        # Sleep for the wait time
        time.sleep(wait_time)

        # Clean up and record
        self._cleanup()
        self.record(tokens)
        return wait_time

    async def async_wait_if_needed(self, tokens: int = 0) -> float:
        """
        Async version of wait_if_needed.

        Awaits asyncio.sleep instead of time.sleep for non-blocking operation.
        Returns wait time in seconds.
        """
        self._cleanup()

        if self.check(tokens):
            self.record(tokens)
            return 0.0

        wait_time = self._calculate_wait_time(tokens)
        if wait_time <= 0:
            self.record(tokens)
            return 0.0

        logger.debug(f"Rate limit (async): waiting {wait_time:.1f}s (tokens={tokens})")
        self._total_requests_blocked += 1

        await asyncio.sleep(wait_time)

        self._cleanup()
        self.record(tokens)
        return wait_time

    # ── Internal ──

    def _cleanup(self) -> int:
        """Remove expired records from the window. Returns count removed."""
        with self._lock:
            if not self._records:
                return 0

            cutoff = time.time() - self.window_seconds
            original = len(self._records)
            while self._records and self._records[0].timestamp < cutoff:
                self._records.popleft()
            return original - len(self._records)

    def _calculate_wait_time(self, tokens: int = 0) -> float:
        """
        Calculate how long to wait until a request can proceed.

        Returns 0 if the request can proceed immediately.
        """
        if not self._records:
            return 0.0

        now = time.time()
        window_start = now - self.window_seconds
        wait_times = []

        # Request-based wait
        if self.max_requests > 0 and len(self._records) >= self.max_requests:
            # Wait until the oldest request expires
            oldest = self._records[0]
            wait = oldest.timestamp + self.window_seconds - now
            if wait > 0:
                wait_times.append(wait)

        # Token-based wait
        if self.max_tokens > 0 and tokens > 0:
            # Collect records within the window
            window_records = [r for r in self._records if r.timestamp >= window_start]
            current_tokens = sum(r.tokens for r in window_records)

            if current_tokens + tokens > self.max_tokens:
                # Calculate how long until enough tokens expire for this request
                # Sort by timestamp, accumulate tokens until we have enough room
                sorted_records = sorted(window_records, key=lambda r: r.timestamp)
                needed = (current_tokens + tokens) - self.max_tokens
                accumulated = 0
                for r in sorted_records:
                    accumulated += r.tokens
                    if accumulated >= needed:
                        wait = r.timestamp + self.window_seconds - now
                        if wait > 0:
                            wait_times.append(wait)
                        break

        return max(wait_times) if wait_times else 0.0

    # ── Stats ──

    def get_current_usage(self) -> dict:
        """Get current rate limit usage statistics."""
        self._cleanup()
        with self._lock:
            window_tokens = sum(r.tokens for r in self._records)
            return {
                "current_requests": len(self._records),
                "max_requests": self.max_requests,
                "current_tokens": window_tokens,
                "max_tokens": self.max_tokens,
                "window_seconds": self.window_seconds,
                "usage_pct_requests": (
                    round(len(self._records) / self.max_requests * 100, 1)
                    if self.max_requests > 0 else 0
                ),
                "usage_pct_tokens": (
                    round(window_tokens / self.max_tokens * 100, 1)
                    if self.max_tokens > 0 else 0
                ),
                "total_requests_blocked": self._total_requests_blocked,
                "total_tokens_used": self._total_tokens_used,
                "rate_limited_count": self._rate_limited_count,
            }

    # ── Adaptive Rate Limiting (Feature 5) ──

    def get_adaptive_limit(self, recent_minutes: int = 5) -> dict:
        """
        Compute an adaptive rate limit recommendation based on recent usage.

        Analyzes the last N minutes of usage and computes a safe limit
        that is 80% of the peak usage seen in that window. This prevents
        sudden bans by automatically smoothing out usage spikes.

        Args:
            recent_minutes: How many minutes of history to analyze

        Returns:
            Dict with:
              - suggested_max_requests: Adjusted max_requests recommendation
              - suggested_max_tokens: Adjusted max_tokens recommendation
              - peak_requests: Highest request count seen in any window
              - peak_tokens: Highest token count seen in any window
              - safety_buffer_pct: Percentage below peak (always 20%%)
              - is_adaptive: Whether adaptive mode is active
        """
        with self._lock:
            now = time.time()
            cutoff = now - min(recent_minutes * 60, self.window_seconds * 3)

            # Get records within the analysis window
            recent = [r for r in self._records if r.timestamp >= cutoff]

            if not recent:
                return {
                    "suggested_max_requests": self.max_requests,
                    "suggested_max_tokens": self.max_tokens,
                    "peak_requests": 0,
                    "peak_tokens": 0,
                    "safety_buffer_pct": 20,
                    "is_adaptive": False,
                }

            # Calculate peak usage
            peak_requests = len(recent)
            peak_tokens = sum(r.tokens for r in recent)

            # Safety buffer: 80%% of peak (20%% headroom)
            safety_factor = 0.8
            suggested_requests = max(
                self.max_requests,
                int(peak_requests / safety_factor) + 1
            ) if peak_requests > 0 else self.max_requests

            suggested_tokens = max(
                self.max_tokens,
                int(peak_tokens / safety_factor) + 100
            ) if peak_tokens > 0 else self.max_tokens

            return {
                "suggested_max_requests": suggested_requests,
                "suggested_max_tokens": suggested_tokens,
                "peak_requests": peak_requests,
                "peak_tokens": peak_tokens,
                "safety_buffer_pct": 20,
                "is_adaptive": True,
                "analysis_window_minutes": recent_minutes,
            }

    def apply_adaptive_limit(self, recent_minutes: int = 5) -> dict:
        """
        Automatically adjust rate limits based on recent usage.

        Calls get_adaptive_limit() and applies the suggested limits
        if they differ from current settings.

        Returns the adaptive limit dict with an 'applied' status field.
        """
        adaptive = self.get_adaptive_limit(recent_minutes)

        if not adaptive["is_adaptive"]:
            adaptive["applied"] = False
            adaptive["reason"] = "No recent usage data"
            return adaptive

        changes = []
        if adaptive["suggested_max_requests"] != self.max_requests:
            old = self.max_requests
            self.max_requests = adaptive["suggested_max_requests"]
            changes.append(f"requests: {old} → {self.max_requests}")

        if adaptive["suggested_max_tokens"] != self.max_tokens:
            old = self.max_tokens
            self.max_tokens = adaptive["suggested_max_tokens"]
            changes.append(f"tokens: {old} → {self.max_tokens}")

        adaptive["applied"] = len(changes) > 0
        adaptive["changes"] = changes

        if changes:
            logger.info(f"Adaptive rate limit applied: {', '.join(changes)}")

        return adaptive

    def get_retry_after(self) -> float:
        """
        Get the time (in seconds) until the oldest request expires.
        Useful for HTTP 429 Retry-After responses.
        """
        self._cleanup()
        if not self._records:
            return 0.0
        oldest = self._records[0]
        wait = oldest.timestamp + self.window_seconds - time.time()
        return max(0.0, wait)

    def reset(self) -> None:
        """Reset all rate limit tracking."""
        with self._lock:
            self._records.clear()
            self._total_requests_blocked = 0
            self._total_tokens_used = 0
            self._rate_limited_count = 0

    def __repr__(self) -> str:
        usage = self.get_current_usage()
        return (
            f"RateLimiter("
            f"requests={usage['current_requests']}/{usage['max_requests']}, "
            f"tokens={usage['current_tokens']}/{usage['max_tokens']})"
        )
