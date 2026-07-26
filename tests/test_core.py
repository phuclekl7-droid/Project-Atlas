"""
Unit tests for the Core module.

Tests:
- Logger setup: creates logger, respects levels, adds handler once
- Exception hierarchy: AssistantError → ConfigurationError, ModelConnectionError, PluginExecutionError
- Utilities: truncate_text, format_timestamp
"""

import logging

import pytest

from src.core import (
    LOG_LEVELS,
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    PluginExecutionError,
    ColoredFormatter,
    format_timestamp,
    setup_logger,
    truncate_text,
)


# ============================================================
# Logger Tests
# ============================================================


class TestSetupLogger:
    def test_creates_logger_with_name(self):
        """Logger should be created with the given name."""
        logger = setup_logger("test-module")
        assert logger.name == "test-module"
        assert logger.level == logging.INFO

    def test_creates_logger_with_custom_level(self):
        """Logger should respect a custom log level."""
        logger = setup_logger("test-debug", level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_creates_logger_with_warning_level(self):
        """Logger should accept WARNING level."""
        logger = setup_logger("test-warn", level="WARNING")
        assert logger.level == logging.WARNING

    def test_invalid_level_defaults_to_info(self):
        """An invalid level string should fall back to INFO."""
        logger = setup_logger("test-invalid", level="NONSENSE")
        assert logger.level == logging.INFO

    def test_adds_stream_handler(self):
        """Logger should have exactly one StreamHandler."""
        logger = setup_logger("test-handler")
        handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(handlers) == 1

    def test_handler_has_colored_formatter(self):
        """The StreamHandler should use ColoredFormatter."""
        logger = setup_logger("test-formatter")
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, ColoredFormatter)

    def test_does_not_duplicate_handlers(self):
        """Calling setup_logger twice on the same name should not add extra handlers."""
        logger = setup_logger("test-no-duplicate")
        original_count = len(logger.handlers)
        logger2 = setup_logger("test-no-duplicate")
        assert len(logger2.handlers) == original_count


class TestColoredFormatter:
    def test_formats_basic_message(self):
        """ColoredFormatter should produce a string output."""
        formatter = ColoredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert isinstance(output, str)
        assert "hello world" in output
        # Should contain ANSI color codes
        assert "\033[" in output

    def test_formats_exception(self):
        """ColoredFormatter should include exception info when present."""
        formatter = ColoredFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="something broke",
                args=(),
                exc_info=sys.exc_info(),
            )
        output = formatter.format(record)
        assert "something broke" in output
        assert "ValueError" in output or "test error" in output


# ============================================================
# Exception Hierarchy Tests
# ============================================================


class TestAssistantError:
    def test_is_exception_subclass(self):
        """AssistantError should inherit from Exception."""
        assert issubclass(AssistantError, Exception)

    def test_default_message(self):
        """Default error should have a sensible message."""
        err = AssistantError()
        assert err.message == "An unexpected error occurred"

    def test_custom_message(self):
        """Custom message should be stored."""
        err = AssistantError("Custom message")
        assert err.message == "Custom message"

    def test_with_details(self):
        """Details should be appended to the message."""
        err = AssistantError("Error", details="Something went wrong")
        assert err.details == "Something went wrong"
        assert "Details: Something went wrong" in str(err)

    def test_without_details(self):
        """Without details, message should be clean."""
        err = AssistantError("Simple error")
        assert err.details is None
        assert str(err) == "Simple error"


class TestConfigurationError:
    def test_is_assistant_error_subclass(self):
        """ConfigurationError should inherit from AssistantError."""
        assert issubclass(ConfigurationError, AssistantError)

    def test_default_message(self):
        """Default should indicate configuration issue."""
        err = ConfigurationError()
        assert "Configuration error" in str(err)


class TestModelConnectionError:
    def test_is_assistant_error_subclass(self):
        """ModelConnectionError should inherit from AssistantError."""
        assert issubclass(ModelConnectionError, AssistantError)

    def test_default_message(self):
        """Default should indicate connection failure."""
        err = ModelConnectionError()
        assert "Failed to connect to model" in str(err)


class TestPluginExecutionError:
    def test_is_assistant_error_subclass(self):
        """PluginExecutionError should inherit from AssistantError."""
        assert issubclass(PluginExecutionError, AssistantError)

    def test_default_message(self):
        """Default should indicate plugin execution failure."""
        err = PluginExecutionError()
        assert "Plugin execution failed" in str(err)

    def test_catch_base_exception(self):
        """Catching AssistantError should catch all derived exceptions."""
        errors = [
            ConfigurationError("config"),
            ModelConnectionError("conn"),
            PluginExecutionError("plugin"),
        ]
        for err in errors:
            assert isinstance(err, AssistantError)


# ============================================================
# Utility Tests
# ============================================================


class TestTruncateText:
    def test_short_text_not_truncated(self):
        """Text shorter than max_length should be returned as-is."""
        text = "Hello, world!"
        result = truncate_text(text, max_length=100)
        assert result == text

    def test_long_text_truncated(self):
        """Text longer than max_length should be truncated with suffix."""
        text = "a" * 100
        result = truncate_text(text, max_length=20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_exact_length_not_truncated(self):
        """Text exactly at max_length should not be truncated."""
        text = "a" * 50
        result = truncate_text(text, max_length=50)
        assert result == text
        assert len(result) == 50

    def test_custom_suffix(self):
        """Custom suffix should be used."""
        text = "a" * 30
        result = truncate_text(text, max_length=10, suffix="[..]")
        assert result.endswith("[..]")

    def test_empty_string(self):
        """Empty string should return empty."""
        assert truncate_text("") == ""


class TestFormatTimestamp:
    def test_returns_string(self):
        """format_timestamp should always return a string."""
        result = format_timestamp()
        assert isinstance(result, str)

    def test_default_format(self):
        """Default format should be YYYY-MM-DD HH:MM:SS."""
        result = format_timestamp()
        assert len(result) == 19  # "2026-07-27 12:34:56"
        assert result[4] == "-"
        assert result[7] == "-"
        assert result[13] == ":"

    def test_without_argument_uses_now(self):
        """Calling without argument should not raise."""
        result = format_timestamp()
        assert isinstance(result, str)
