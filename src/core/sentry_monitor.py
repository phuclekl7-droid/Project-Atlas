"""
Sentry Error Monitoring (Feature #90).
Captures, aggregates, and reports application errors.

Provides:
- Error capture with context (session, action, provider)
- Error aggregation and deduplication
- In-memory error log as fallback when Sentry SDK isn't available
- Integration with Streamlit UI for error display

Usage:
    monitor = SentryMonitor()
    monitor.capture_exception(error, context={"action": "send_message"})
    errors = monitor.get_recent_errors(limit=5)
"""

import os
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.core import setup_logger

logger = setup_logger("sentry_monitor")

# Optional Sentry SDK
try:
    import sentry_sdk
    from sentry_sdk import configure_scope

    _HAS_SENTRY = True
except ImportError:
    _HAS_SENTRY = False
    configure_scope = None


@dataclass
class CapturedError:
    """
    Represents a captured error with context.

    Attributes:
        id: Unique error ID
        message: Error message
        type: Error type/class name
        timestamp: When the error occurred
        context: Additional context dict
        traceback_str: Full traceback as string
        count: Number of times this error was seen
    """

    id: str = ""
    message: str = ""
    type: str = ""
    timestamp: float = 0.0
    context: dict = field(default_factory=dict)
    traceback_str: str = ""
    count: int = 1

    @property
    def formatted_time(self) -> str:
        """Get formatted timestamp."""
        return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")


class SentryMonitor:
    """
    Error monitoring and capture system.

    Uses Sentry SDK when available, falls back to in-memory error log.

    Usage:
        monitor = SentryMonitor(dsn="https://...@sentry.io/...")
        monitor.init_sentry()  # Initialize Sentry SDK

        try:
            result = risky_operation()
        except Exception as e:
            monitor.capture_exception(e, context={"operation": "risky"})

        # Get recent errors for UI display
        errors = monitor.get_recent_errors()
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        environment: str = "development",
        max_errors: int = 100,
        enable_in_memory: bool = True,
    ):
        """
        Initialize the Sentry monitor.

        Args:
            dsn: Sentry DSN (from environment variable SENTRY_DSN if not provided)
            environment: Environment name (development, production, etc.)
            max_errors: Maximum in-memory error log entries
            enable_in_memory: Whether to keep in-memory error log
        """
        self._dsn = dsn or os.environ.get("SENTRY_DSN", "")
        self._environment = environment
        self._max_errors = max_errors
        self._enable_in_memory = enable_in_memory

        self._initialized = False
        self._errors: list[CapturedError] = []
        self._error_index: dict[str, CapturedError] = {}  # Dedup by message+type
        self._stats = {
            "total_captured": 0,
            "unique_errors": 0,
            "last_error_time": 0.0,
            "start_time": time.time(),
        }
        self._lock = threading.Lock()

    def init_sentry(self) -> bool:
        """
        Initialize the Sentry SDK if DSN is configured.

        Returns:
            True if Sentry was initialized successfully
        """
        if self._initialized:
            return True

        if not self._dsn:
            logger.info("No Sentry DSN configured — using in-memory error log only")
            return False

        if not _HAS_SENTRY:
            logger.warning("sentry_sdk not installed. Install: pip install sentry-sdk")
            return False

        try:
            sentry_sdk.init(
                dsn=self._dsn,
                environment=self._environment,
                traces_sample_rate=0.1,
                send_default_pii=False,
            )
            self._initialized = True
            logger.info(f"Sentry initialized (env={self._environment})")
            return True
        except Exception as e:
            logger.warning(f"Sentry init failed: {e}")
            return False

    def set_context(self, key: str, value: Any) -> None:
        """
        Set Sentry context tag (if Sentry is initialized).

        Args:
            key: Context key
            value: Context value
        """
        if self._initialized and _HAS_SENTRY and configure_scope:
            try:
                with configure_scope() as scope:
                    scope.set_tag(key, str(value))
            except Exception:
                pass

    def capture_exception(
        self,
        error: Exception,
        context: Optional[dict] = None,
        level: str = "error",
    ) -> Optional[str]:
        """
        Capture an exception with context.

        Args:
            error: The exception to capture
            context: Additional context dict (action, session, provider, etc.)
            level: Severity level (debug, info, warning, error, critical)

        Returns:
            Error ID string if captured, None if failed
        """
        exc_type = type(error).__name__
        exc_message = str(error) or repr(error)
        tb_str = traceback.format_exc()

        # Generate error ID
        dedup_key = f"{exc_type}:{exc_message[:100]}"
        error_id = f"err_{int(time.time())}_{hash(dedup_key) % 10000:04d}"

        # Capture in Sentry
        if self._initialized and _HAS_SENTRY:
            try:
                with sentry_sdk.push_scope() as scope:
                    if context:
                        for key, value in context.items():
                            scope.set_tag(key, str(value)[:200])
                    scope.set_level(level)
                    sentry_sdk.capture_exception(error)
            except Exception as e:
                logger.debug(f"Sentry capture failed: {e}")

        # In-memory log
        if self._enable_in_memory:
            with self._lock:
                self._stats["total_captured"] += 1
                self._stats["last_error_time"] = time.time()

                # Check for duplicate
                existing = self._error_index.get(dedup_key)
                if existing:
                    existing.count += 1
                    # Update timestamp but keep original ID
                    existing.timestamp = time.time()
                else:
                    captured = CapturedError(
                        id=error_id,
                        message=exc_message,
                        type=exc_type,
                        timestamp=time.time(),
                        context=context or {},
                        traceback_str=tb_str,
                        count=1,
                    )
                    self._errors.append(captured)
                    self._error_index[dedup_key] = captured
                    self._stats["unique_errors"] += 1

                # Trim
                if len(self._errors) > self._max_errors:
                    removed = self._errors.pop(0)
                    # Remove from index too
                    old_key = f"{removed.type}:{removed.message[:100]}"
                    self._error_index.pop(old_key, None)

        return error_id

    def capture_message(
        self,
        message: str,
        context: Optional[dict] = None,
        level: str = "info",
    ) -> Optional[str]:
        """Capture a message/event (not an exception)."""
        dedup_key = f"msg:{message[:100]}"
        error_id = f"msg_{int(time.time())}_{hash(dedup_key) % 10000:04d}"

        if self._initialized and _HAS_SENTRY:
            try:
                with sentry_sdk.push_scope() as scope:
                    if context:
                        for key, value in context.items():
                            scope.set_tag(key, str(value)[:200])
                    sentry_sdk.capture_message(message, level=level)
            except Exception as e:
                logger.debug(f"Sentry message capture failed: {e}")

        if self._enable_in_memory:
            with self._lock:
                self._stats["total_captured"] += 1
                captured = CapturedError(
                    id=error_id,
                    message=message,
                    type="Message",
                    timestamp=time.time(),
                    context=context or {},
                    count=1,
                )
                self._errors.append(captured)

                if len(self._errors) > self._max_errors:
                    self._errors.pop(0)

        return error_id

    # ── Query Methods ──

    def get_recent_errors(
        self,
        limit: int = 10,
        min_level: str = "warning",
    ) -> list[CapturedError]:
        """Get the most recent errors, sorted by time descending."""
        with self._lock:
            # Errors are already in chronological order (oldest first)
            recent = list(reversed(self._errors))
            return recent[:limit]

    def get_errors_by_type(self, error_type: str) -> list[CapturedError]:
        """Get all errors of a specific type."""
        with self._lock:
            return [e for e in self._errors if e.type == error_type]

    def get_error_summary(self) -> list[dict]:
        """Get a summary of errors grouped by type."""
        with self._lock:
            summary: dict[str, dict] = {}
            for err in self._errors:
                if err.type not in summary:
                    summary[err.type] = {
                        "type": err.type,
                        "count": 0,
                        "last_seen": 0.0,
                        "example_message": err.message[:100],
                    }
                summary[err.type]["count"] += err.count
                summary[err.type]["last_seen"] = max(
                    summary[err.type]["last_seen"], err.timestamp
                )

            return sorted(summary.values(), key=lambda x: -x["count"])

    def get_stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            "total_captured": self._stats["total_captured"],
            "unique_errors": self._stats["unique_errors"],
            "in_memory_count": len(self._errors),
            "sentry_initialized": self._initialized,
            "sentry_available": _HAS_SENTRY,
            "dsn_configured": bool(self._dsn),
            "uptime_seconds": round(time.time() - self._stats["start_time"], 1),
        }

    def clear_errors(self) -> int:
        """Clear all in-memory errors. Returns count cleared."""
        with self._lock:
            count = len(self._errors)
            self._errors.clear()
            self._error_index.clear()
            return count
