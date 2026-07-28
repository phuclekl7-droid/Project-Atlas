"""
Tests for Feature #77: Session Expiration Auto Lock.
"""

import time

import pytest

from src.core.session_locker import SessionLocker, LockState, LockEvent


class TestSessionLocker:
    """Tests for SessionLocker class."""

    def test_initial_state(self):
        locker = SessionLocker(timeout_minutes=15)
        assert locker.state == LockState.UNLOCKED
        assert locker.is_unlocked
        assert not locker.is_locked

    def test_manual_lock(self):
        locker = SessionLocker()
        assert locker.lock()
        assert locker.is_locked
        assert locker.state == LockState.LOCKED

    def test_double_lock_fails(self):
        locker = SessionLocker()
        locker.lock()
        assert not locker.lock()

    def test_manual_unlock(self):
        locker = SessionLocker()
        locker.lock()
        assert locker.unlock()
        assert locker.is_unlocked

    def test_unlock_when_not_locked(self):
        locker = SessionLocker()
        assert not locker.unlock()

    def test_idle_tracking(self):
        locker = SessionLocker()
        time.sleep(0.01)
        assert locker.idle_seconds > 0
        assert locker.idle_minutes > 0

    def test_update_activity(self):
        locker = SessionLocker()
        time.sleep(0.02)
        locker.update_activity()
        assert locker.idle_seconds < 0.05

    def test_remaining_time(self):
        locker = SessionLocker(timeout_minutes=10)
        remaining = locker.remaining_seconds
        assert remaining > 0
        assert abs(remaining - 600) < 1  # 10 min = 600 seconds

    def test_reset(self):
        locker = SessionLocker()
        locker.lock()
        locker.reset()
        assert locker.is_unlocked
        assert locker.idle_seconds < 0.1

    def test_timeout_auto_lock(self):
        locker = SessionLocker(timeout_minutes=0)  # Immediate timeout
        time.sleep(0.01)
        assert locker.check_timeout()  # Should auto-lock
        assert locker.is_locked

    def test_no_timeout_with_activity(self):
        locker = SessionLocker(timeout_minutes=1)
        locker.update_activity()
        assert not locker.check_timeout()

    def test_set_timeout(self):
        locker = SessionLocker(timeout_minutes=15)
        locker.set_timeout(30)
        assert locker.timeout_minutes == 30
        assert abs(locker.remaining_seconds - 1800) < 1

    def test_password_protection(self):
        locker = SessionLocker(timeout_minutes=15, require_password=True, password="secret")
        locker.lock()
        assert not locker.unlock("wrong")
        assert locker.unlock("secret")
        assert locker.is_unlocked

    def test_set_password(self):
        locker = SessionLocker()
        locker.set_password("newpass")
        assert locker.password_required
        locker.lock()
        assert locker.unlock("newpass")

    def test_get_stats(self):
        locker = SessionLocker(timeout_minutes=10)
        locker.lock()
        stats = locker.get_stats()
        assert stats["state"] == "locked"
        assert stats["timeout_minutes"] == 10

    def test_get_events(self):
        locker = SessionLocker()
        locker.lock(reason="test_lock")
        events = locker.get_events()
        assert len(events) >= 1
        assert events[0].event_type == "lock"

    def test_monitoring_start_stop(self):
        locker = SessionLocker(timeout_minutes=15)
        locker.start_monitoring()
        assert locker.get_stats()["monitoring"]
        locker.stop_monitoring()
        assert not locker.get_stats()["monitoring"]

    def test_is_expired_alias(self):
        locker = SessionLocker()
        assert not locker.is_expired()
        locker.lock()
        assert locker.is_expired()
