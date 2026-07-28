"""
Audit Log System (Feature 76): Records all significant operations in the app.

Logs operations to a structured JSON file (audit.log) for security,
debugging, and usage analysis. Each entry contains:
  - timestamp: ISO 8601 datetime
  - event_type: The type of operation
  - user: User identifier (session_id or user_id)
  - details: Operation-specific data (safe, no PII)
  - provider: Model provider used (if applicable)
  - tokens: Token count (if applicable)
  - latency_ms: Execution time (if applicable)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Optional

from src.core import setup_logger

logger = setup_logger("audit")

_AUDIT_LOG_PATH: Optional[str] = None
_AUDIT_LOG_FILE: Optional[Path] = None
_WRITE_LOCK = Lock()
_MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB max before rotation


def configure_audit_log(path: str = "data/audit.log") -> None:
    """Set the audit log file path.

    Args:
        path: Path to the audit log file
    """
    global _AUDIT_LOG_PATH, _AUDIT_LOG_FILE
    _AUDIT_LOG_PATH = path
    _AUDIT_LOG_FILE = Path(path)
    _AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Audit log configured: {path}")


def _rotate_if_needed() -> None:
    """Rotate the audit log file if it exceeds the maximum size."""
    global _AUDIT_LOG_FILE
    if _AUDIT_LOG_FILE is None or not _AUDIT_LOG_FILE.exists():
        return

    try:
        if _AUDIT_LOG_FILE.stat().st_size > _MAX_LOG_SIZE_BYTES:
            rotated = _AUDIT_LOG_FILE.with_suffix(".log.1")
            if rotated.exists():
                rotated.unlink()
            _AUDIT_LOG_FILE.rename(rotated)
            logger.info(f"Audit log rotated: {_AUDIT_LOG_FILE} -> {rotated}")
    except OSError as e:
        logger.warning(f"Audit log rotation failed: {e}")


def log_event(
    event_type: str,
    details: Optional[dict[str, Any]] = None,
    user: str = "",
    provider: str = "",
    tokens: int = 0,
    latency_ms: float = 0.0,
    session_id: str = "",
) -> None:
    """Record a single audit event.

    All sensitive data (API keys, passwords, message content) is EXCLUDED
    from the log. Only metadata is recorded.

    Args:
        event_type: Type of event (e.g., 'chat_message', 'plugin_exec', 'model_call')
        details: Safe metadata dict (no PII, no secrets)
        user: User identifier (session ID or username)
        provider: Model provider used (ollama, openai, gemini, mock)
        tokens: Number of tokens used (0 if not applicable)
        latency_ms: Latency in milliseconds (0 if not applicable)
        session_id: Chat session ID
    """
    if _AUDIT_LOG_FILE is None:
        configure_audit_log()

    entry = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "event_type": event_type,
        "user": user[:64] if user else "",
        "session_id": session_id[:16] if session_id else "",
        "provider": provider,
        "tokens": tokens,
        "latency_ms": round(latency_ms, 2),
        "details": details or {},
    }

    with _WRITE_LOCK:
        try:
            _rotate_if_needed()
            with open(str(_AUDIT_LOG_FILE), "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning(f"Failed to write audit log: {e}")


def get_recent_events(
    limit: int = 100,
    event_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Read recent audit log entries, newest first.

    Args:
        limit: Maximum number of entries to return
        event_type: Optional filter by event type

    Returns:
        List of audit entry dicts
    """
    if _AUDIT_LOG_FILE is None or not _AUDIT_LOG_FILE.exists():
        return []

    events: list[dict[str, Any]] = []
    try:
        with _WRITE_LOCK:
            with open(str(_AUDIT_LOG_FILE), "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        if event_type and event.get("event_type") != event_type:
                            continue
                        events.append(event)
                    except json.JSONDecodeError:
                        continue

        # Return newest first (most recent at the top)
        events.reverse()
        return events[:limit]

    except OSError as e:
        logger.warning(f"Failed to read audit log: {e}")
        return []


def get_stats() -> dict[str, Any]:
    """Get audit log statistics.

    Returns:
        Dict with total_events, unique_event_types, oldest, newest
    """
    events = get_recent_events(limit=10000)
    if not events:
        return {
            "total_events": 0,
            "unique_event_types": [],
            "oldest": "",
            "newest": "",
        }

    event_types = set(e.get("event_type", "") for e in events)
    return {
        "total_events": len(events),
        "unique_event_types": sorted(event_types),
        "oldest": events[-1].get("timestamp", "") if events else "",
        "newest": events[0].get("timestamp", "") if events else "",
        "log_file": str(_AUDIT_LOG_FILE) if _AUDIT_LOG_FILE else "",
    }
