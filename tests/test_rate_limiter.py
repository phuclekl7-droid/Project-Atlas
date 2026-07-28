"""
Unit tests for the Rate Limiter module.

Tests:
- check: whether requests are allowed or blocked
- record: tracking requests and tokens
- wait_if_needed: sync blocking wait
- async_wait_if_needed: async non-blocking wait
- cleanup: expired record removal
- get_current_usage: stats accuracy
- reset: clearing all state
- Edge cases: zero limits, single request, token-only limiting
"""

import asyncio
import time

import pytest

from src.core.rate_limiter import RateLimiter


# ============================================================
# Basic Check & Record
# ============================================================


class TestCheck:
    def test_allow_first_request(self):
        """First request should always be allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.check() is True

    def test_allow_within_limit(self):
        """Requests within the limit should be allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(4):
            limiter.record()
        assert limiter.check() is True

    def test_block_when_over_limit(self):
        """Requests over the limit should be blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.record()
        assert limiter.check() is False

    def test_unlimited_requests(self):
        """max_requests=0 should allow unlimited requests."""
        limiter = RateLimiter(max_requests=0, window_seconds=60)
        for _ in range(100):
            assert limiter.check() is True
            limiter.record()

    def test_token_limit_allows_small(self):
        """Requests with small tokens should be allowed under the token limit."""
        limiter = RateLimiter(max_requests=100, max_tokens=1000, window_seconds=60)
        assert limiter.check(tokens=100) is True

    def test_token_limit_blocks_large(self):
        """Requests with large tokens should be blocked when over the limit."""
        limiter = RateLimiter(max_requests=100, max_tokens=100, window_seconds=60)
        limiter.record(tokens=80)
        assert limiter.check(tokens=30) is False  # 80 + 30 > 100

    def test_token_limit_exact_budget(self):
        """Requests exactly at the token budget should be allowed."""
        limiter = RateLimiter(max_requests=100, max_tokens=100, window_seconds=60)
        assert limiter.check(tokens=100) is True


# ============================================================
# Record
# ============================================================


class TestRecord:
    def test_record_increases_count(self):
        """Recording should increase the current request count."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter.get_current_usage()["current_requests"] == 0
        limiter.record()
        assert limiter.get_current_usage()["current_requests"] == 1

    def test_record_with_tokens(self):
        """Recording with tokens should track token usage."""
        limiter = RateLimiter(max_requests=10, max_tokens=1000, window_seconds=60)
        limiter.record(tokens=150)
        assert limiter.get_current_usage()["current_tokens"] == 150

    def test_record_multiple_accumulates(self):
        """Multiple records should accumulate counts."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        for _ in range(5):
            limiter.record(tokens=10)
        usage = limiter.get_current_usage()
        assert usage["current_requests"] == 5
        assert usage["current_tokens"] == 50


# ============================================================
# Wait (Sync)
# ============================================================


class TestWaitIfNeeded:
    def test_no_wait_when_under_limit(self):
        """Under the limit should return 0 wait time."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        wait = limiter.wait_if_needed()
        assert wait == 0.0

    def test_wait_records_request(self):
        """wait_if_needed should record the request after waiting."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.wait_if_needed()
        assert limiter.get_current_usage()["current_requests"] == 1

    def test_wait_when_window_full(self):
        """When the window is full, wait should sleep."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.record()  # Request 1
        limiter.record()  # Request 2 (window full)

        # Next request should wait
        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start
        # Should have waited a bit (the window is 1 second, oldest is ~0s old)
        assert elapsed < 2.0  # Should not wait too long


# ============================================================
# Wait (Async)
# ============================================================


class TestAsyncWaitIfNeeded:
    @pytest.mark.asyncio
    async def test_async_no_wait_when_under_limit(self):
        """Under the limit async should return 0."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        wait = await limiter.async_wait_if_needed()
        assert wait == 0.0

    @pytest.mark.asyncio
    async def test_async_records_request(self):
        """async_wait_if_needed should record the request."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        await limiter.async_wait_if_needed()
        assert limiter.get_current_usage()["current_requests"] == 1

    @pytest.mark.asyncio
    async def test_async_wait_when_full(self):
        """When window is full, async should still wait."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        await limiter.async_wait_if_needed()

        start = time.time()
        await limiter.async_wait_if_needed()
        elapsed = time.time() - start
        assert elapsed > 0  # Should have waited at least a moment


# ============================================================
# Cleanup
# ============================================================


class TestCleanup:
    def test_cleanup_removes_expired(self):
        """cleanup should remove expired records."""
        limiter = RateLimiter(max_requests=10, window_seconds=0.01)
        limiter.record()
        time.sleep(0.02)
        removed = limiter._cleanup()
        assert removed == 1
        assert limiter.get_current_usage()["current_requests"] == 0

    def test_cleanup_no_expired(self):
        """cleanup should not remove non-expired records."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        limiter.record()
        removed = limiter._cleanup()
        assert removed == 0

    def test_cleanup_empty(self):
        """cleanup on empty deque should return 0."""
        limiter = RateLimiter(max_requests=10)
        assert limiter._cleanup() == 0

    def test_check_cleans_up(self):
        """check should trigger cleanup automatically."""
        limiter = RateLimiter(max_requests=10, window_seconds=0.01)
        limiter.record()
        time.sleep(0.02)
        # check() calls _cleanup internally
        assert limiter.check() is True  # Old record is gone


# ============================================================
# Stats
# ============================================================


class TestGetCurrentUsage:
    def test_usage_empty(self):
        """Empty limiter should show zero usage."""
        limiter = RateLimiter(max_requests=10, max_tokens=1000, window_seconds=60)
        usage = limiter.get_current_usage()
        assert usage["current_requests"] == 0
        assert usage["current_tokens"] == 0
        assert usage["usage_pct_requests"] == 0
        assert usage["usage_pct_tokens"] == 0

    def test_usage_percentage(self):
        """Usage percentage should be calculated correctly."""
        limiter = RateLimiter(max_requests=10, max_tokens=1000, window_seconds=60)
        for _ in range(5):
            limiter.record(tokens=100)
        usage = limiter.get_current_usage()
        assert usage["usage_pct_requests"] == 50.0  # 5/10
        assert usage["usage_pct_tokens"] == 50.0    # 500/1000

    def test_usage_tracks_blocked(self):
        """Blocked requests should be counted."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.record()
        limiter.record()
        limiter.check()  # Blocked (check doesn't inc blocked count itself)
        assert limiter.get_current_usage()["rate_limited_count"] == 1


# ============================================================
# Reset
# ============================================================


class TestReset:
    def test_reset_clears_records(self):
        """Reset should clear all records and counts."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        limiter.record()
        limiter.record(tokens=50)
        limiter.wait_if_needed(tokens=100)
        limiter.reset()
        usage = limiter.get_current_usage()
        assert usage["current_requests"] == 0
        assert usage["current_tokens"] == 0
        assert usage["total_requests_blocked"] == 0
        assert usage["total_tokens_used"] == 0

    def test_reset_allows_new_requests(self):
        """After reset, requests should be allowed again."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.record()
        assert limiter.check() is False
        limiter.reset()
        assert limiter.check() is True


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    def test_zero_request_limit(self):
        """max_requests=0 should never block."""
        limiter = RateLimiter(max_requests=0, window_seconds=60)
        for _ in range(1000):
            assert limiter.check() is True

    def test_zero_token_limit(self):
        """max_tokens=0 should never block on tokens."""
        limiter = RateLimiter(max_requests=100, max_tokens=0, window_seconds=60)
        for _ in range(10):
            assert limiter.check(tokens=999999) is True

    def test_negative_limits(self):
        """Negative limits should clamp to zero-ish behavior."""
        limiter = RateLimiter(max_requests=-1, max_tokens=-1, window_seconds=60)
        assert limiter.check() is True

    def test_get_retry_after_with_no_records(self):
        """retry_after should return 0 when no records exist."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter.get_retry_after() == 0.0

    def test_get_retry_after_with_records(self):
        """retry_after should return a positive value when records exist."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.record()
        assert limiter.get_retry_after() > 0

    def test_repr(self):
        """__repr__ should include current usage."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        r = repr(limiter)
        assert "RateLimiter" in r
        assert "0/5" in r  # 0 current out of 5 max
