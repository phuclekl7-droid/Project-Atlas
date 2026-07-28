"""
Tests for Feature #90: Sentry Error Monitoring.
"""

import pytest

from src.core.sentry_monitor import SentryMonitor, CapturedError


class TestSentryMonitor:
    """Tests for SentryMonitor class."""

    def test_initialization(self):
        monitor = SentryMonitor()
        stats = monitor.get_stats()
        assert stats["total_captured"] == 0
        assert not stats["dsn_configured"]

    def test_init_with_dsn(self):
        monitor = SentryMonitor(dsn="https://key@sentry.io/project")
        assert monitor.get_stats()["dsn_configured"]

    def test_capture_exception(self):
        monitor = SentryMonitor()
        error_id = monitor.capture_exception(
            ValueError("test error"),
            context={"action": "test"},
        )
        assert error_id is not None
        assert error_id.startswith("err_")

    def test_capture_exception_increments_count(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("test"))
        assert monitor.get_stats()["total_captured"] == 1

    def test_capture_multiple_exceptions(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("err1"))
        monitor.capture_exception(TypeError("err2"))
        assert monitor.get_stats()["total_captured"] == 2
        assert monitor.get_stats()["unique_errors"] == 2

    def test_capture_deduplicates_similar_errors(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("same error"))
        monitor.capture_exception(ValueError("same error"))
        assert monitor.get_stats()["unique_errors"] == 1

    def test_capture_message(self):
        monitor = SentryMonitor()
        msg_id = monitor.capture_message("User logged in", level="info")
        assert msg_id is not None
        assert msg_id.startswith("msg_")

    def test_get_recent_errors(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("error 1"))
        monitor.capture_exception(TypeError("error 2"))
        errors = monitor.get_recent_errors(limit=5)
        assert len(errors) == 2

    def test_get_recent_errors_limit(self):
        monitor = SentryMonitor()
        for i in range(5):
            monitor.capture_exception(ValueError(f"error {i}"))
        errors = monitor.get_recent_errors(limit=2)
        assert len(errors) == 2

    def test_get_errors_by_type(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("val err"))
        monitor.capture_exception(TypeError("typ err"))
        monitor.capture_exception(ValueError("val err 2"))
        errors = monitor.get_errors_by_type("ValueError")
        assert len(errors) == 2

    def test_get_error_summary(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("test"))
        summary = monitor.get_error_summary()
        assert len(summary) >= 1
        assert summary[0]["type"] == "ValueError"

    def test_clear_errors(self):
        monitor = SentryMonitor()
        monitor.capture_exception(ValueError("test"))
        cleared = monitor.clear_errors()
        assert cleared >= 1
        assert monitor.get_stats()["in_memory_count"] == 0

    def test_max_errors_trimming(self):
        monitor = SentryMonitor(max_errors=3)
        for i in range(10):
            monitor.capture_exception(ValueError(f"error {i}"))
        assert monitor.get_stats()["in_memory_count"] <= 3

    def test_get_stats(self):
        monitor = SentryMonitor()
        stats = monitor.get_stats()
        assert "total_captured" in stats
        assert "sentry_initialized" in stats
        assert "sentry_available" in stats
        assert "uptime_seconds" in stats

    def test_set_context(self):
        monitor = SentryMonitor()
        # Should not raise even without sentry initialized
        monitor.set_context("key", "value")

    def test_captured_error_properties(self):
        error = CapturedError(
            id="err_001",
            message="test error",
            type="ValueError",
            timestamp=1000000,
        )
        assert error.formatted_time is not None
