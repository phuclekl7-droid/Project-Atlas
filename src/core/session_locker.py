"""
Session Expiration Auto Lock (Feature #77).
Auto-locks the app after a period of inactivity.

Provides:
- Idle time tracking
- Lock/unlock state management
- Integration with Streamlit session state
- Configurable timeout

Usage:
    locker = SessionLocker(timeout_minutes=15)
    locker.update_activity()  # Call on every user action
    if locker.is_locked():
        # Show lock screen
        pass
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.core import setup_logger

logger = setup_logger("session_locker")


class LockState(Enum):
    """Current lock state of the session."""
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    LOCKING = "locking"  # Transition state


@dataclass
class LockEvent:
    """Record of a lock/unlock event."""
    timestamp: float = 0.0
    event_type: str = ""  # "lock", "unlock", "timeout"
    reason: str = ""


class SessionLocker:
    """
    Manages automatic session locking after inactivity.

    Tracks user activity and automatically locks the session
    after a configurable timeout period.

    Usage:
        locker = SessionLocker(timeout_minutes=15)
        locker.update_activity()  # On each user interaction
        if locker.is_locked():
            show_lock_screen()
        locker.unlock("password")  # To unlock
    """

    def __init__(
        self,
        timeout_minutes: int = 15,
        check_interval_seconds: float = 5.0,
        require_password: bool = False,
        password: str = "",
    ):
        """
        Initialize the session locker.

        Args:
            timeout_minutes: Minutes of inactivity before auto-lock
            check_interval_seconds: How often to check for timeout
            require_password: Whether a password is needed to unlock
            password: Optional password for unlocking
        """
        self.timeout_minutes = timeout_minutes
        self._timeout_seconds = timeout_minutes * 60
        self._check_interval = check_interval_seconds
        self._require_password = require_password
        self._password = password

        self._state = LockState.UNLOCKED
        self._last_activity: float = time.time()
        self._events: list[LockEvent] = []
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitoring = False

    # ── Activity Tracking ──

    def update_activity(self) -> None:
        """Record user activity, resetting the idle timer."""
        with self._lock:
            self._last_activity = time.time()
            if self._state == LockState.LOCKING:
                self._state = LockState.UNLOCKED
                logger.debug("Activity detected during locking — staying unlocked")

    @property
    def idle_seconds(self) -> float:
        """Get seconds since last user activity."""
        return time.time() - self._last_activity

    @property
    def idle_minutes(self) -> float:
        """Get minutes since last user activity."""
        return self.idle_seconds / 60.0

    @property
    def remaining_seconds(self) -> float:
        """Get seconds remaining before auto-lock."""
        remaining = self._timeout_seconds - self.idle_seconds
        return max(0.0, remaining)

    @property
    def remaining_minutes(self) -> float:
        """Get minutes remaining before auto-lock."""
        return self.remaining_seconds / 60.0

    # ── Lock State ──

    @property
    def is_locked(self) -> bool:
        """Check if the session is currently locked."""
        return self._state == LockState.LOCKED

    @property
    def is_unlocked(self) -> bool:
        """Check if the session is currently unlocked."""
        return self._state == LockState.UNLOCKED

    @property
    def state(self) -> LockState:
        """Get the current lock state."""
        return self._state

    def lock(self, reason: str = "manual") -> bool:
        """
        Manually lock the session.

        Args:
            reason: Reason for locking (e.g., "manual", "timeout")

        Returns:
            True if successfully locked
        """
        with self._lock:
            if self._state == LockState.LOCKED:
                return False
            self._state = LockState.LOCKED
            self._events.append(LockEvent(
                timestamp=time.time(),
                event_type="lock",
                reason=reason,
            ))
            logger.info(f"Session locked: {reason}")
            return True

    def unlock(self, password: str = "") -> bool:
        """
        Unlock the session.

        Args:
            password: Required if require_password is True

        Returns:
            True if successfully unlocked
        """
        with self._lock:
            if self._state != LockState.LOCKED:
                return False

            if self._require_password and password != self._password:
                logger.debug("Unlock failed: incorrect password")
                return False

            self._state = LockState.UNLOCKED
            self._last_activity = time.time()
            self._events.append(LockEvent(
                timestamp=time.time(),
                event_type="unlock",
                reason="manual",
            ))
            logger.info("Session unlocked")
            return True

    def reset(self) -> None:
        """Reset the locker to unlocked state with fresh timer."""
        with self._lock:
            self._state = LockState.UNLOCKED
            self._last_activity = time.time()
            logger.debug("Session locker reset")

    # ── Auto-Lock Monitoring ──

    def start_monitoring(self) -> None:
        """Start background monitoring thread for auto-lock."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
        )
        self._monitor_thread.start()
        logger.debug(f"Auto-lock monitoring started (timeout={self.timeout_minutes}min)")

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
            self._monitor_thread = None
        logger.debug("Auto-lock monitoring stopped")

    def _monitor_loop(self) -> None:
        """Background loop that checks for inactivity timeout."""
        while self._monitoring:
            try:
                self.check_timeout()
            except Exception as e:
                logger.warning(f"Monitor check error: {e}")
            time.sleep(self._check_interval)

    def check_timeout(self) -> bool:
        """
        Check if the session should be locked due to inactivity.
        Called automatically by monitor, can also be called manually.

        Returns:
            True if session was locked due to timeout
        """
        if self._state != LockState.UNLOCKED:
            return False

        if self.idle_seconds >= self._timeout_seconds:
            with self._lock:
                self._state = LockState.LOCKED
                self._events.append(LockEvent(
                    timestamp=time.time(),
                    event_type="timeout",
                    reason=f"Auto-lock after {self.timeout_minutes}min of inactivity",
                ))
                logger.info(f"Session auto-locked after {self.idle_minutes:.1f}min idle")
            return True

        return False

    # ── Configuration ──

    def set_timeout(self, minutes: int) -> None:
        """Change the auto-lock timeout duration."""
        self.timeout_minutes = max(1, minutes)
        self._timeout_seconds = self.timeout_minutes * 60
        logger.info(f"Auto-lock timeout set to {minutes}min")

    def set_password(self, password: str) -> None:
        """Set or change the unlock password."""
        self._require_password = bool(password)
        self._password = password
        logger.debug("Unlock password updated")

    @property
    def password_required(self) -> bool:
        """Whether a password is required to unlock."""
        return self._require_password

    # ── History & Stats ──

    def get_events(self, limit: int = 10) -> list[LockEvent]:
        """Get recent lock/unlock events."""
        return sorted(self._events, key=lambda e: -e.timestamp)[:limit]

    def get_stats(self) -> dict:
        """Get locker statistics."""
        with self._lock:
            return {
                "state": self._state.value,
                "timeout_minutes": self.timeout_minutes,
                "idle_seconds": round(self.idle_seconds, 1),
                "remaining_seconds": round(self.remaining_seconds, 1),
                "require_password": self._require_password,
                "total_events": len(self._events),
                "monitoring": self._monitoring,
            }

    def is_expired(self) -> bool:
        """Alias for is_locked — used by external checkers."""
        return self.is_locked
