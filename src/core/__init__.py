"""
Core module: Contains shared utilities, logger configuration, base exceptions, and core interfaces.
"""

import logging
import sys
from datetime import datetime
from typing import Optional


# ============================================================
# Logging Configuration
# ============================================================

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Console color codes (ANSI)
_COLORS = {
    "DEBUG": "\033[36m",      # Cyan
    "INFO": "\033[32m",       # Green
    "WARNING": "\033[33m",    # Yellow
    "ERROR": "\033[31m",      # Red
    "CRITICAL": "\033[41m",   # Red background
    "RESET": "\033[0m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
}


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds ANSI colors to console output."""

    def format(self, record: logging.LogRecord) -> str:
        levelname = record.levelname
        color = _COLORS.get(levelname, _COLORS["RESET"])
        reset = _COLORS["RESET"]
        dim = _COLORS["DIM"]
        bold = _COLORS["BOLD"]

        # Short module name
        module = record.name.split(".")[-1] if record.name else "root"

        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        formatted = (
            f"{dim}{timestamp}{reset} "
            f"{color}{bold}{levelname:<8}{reset} "
            f"{dim}[{module}]{reset} "
            f"{record.getMessage()}"
        )

        if record.exc_info and record.exc_info[0] is not None:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def setup_logger(name: str = "assistant", level: str = "INFO") -> logging.Logger:
    """
    Configure and return a logger with colored console output.

    Args:
        name: Logger name (usually module name)
        level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL

    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger(name)
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Avoid adding duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        handler.setFormatter(ColoredFormatter())
        logger.addHandler(handler)

    return logger


# ============================================================
# Base Exceptions
# ============================================================


class AssistantError(Exception):
    """Base exception for all Personal AI Assistant errors."""

    def __init__(self, message: str = "An unexpected error occurred", details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class ConfigurationError(AssistantError):
    """Raised when there is a configuration or environment issue."""

    def __init__(self, message: str = "Configuration error", details: Optional[str] = None):
        super().__init__(message=message, details=details)


class ModelConnectionError(AssistantError):
    """Raised when the model router fails to connect to an LLM provider."""

    def __init__(self, message: str = "Failed to connect to model", details: Optional[str] = None):
        super().__init__(message=message, details=details)


class PluginExecutionError(AssistantError):
    """Raised when a plugin fails during execution."""

    def __init__(self, message: str = "Plugin execution failed", details: Optional[str] = None):
        super().__init__(message=message, details=details)


# ============================================================
# Utilities
# ============================================================


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to max_length with a suffix."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)].rstrip() + suffix


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format a datetime object to ISO-like string."""
    dt = dt or datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")
