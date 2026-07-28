"""Tests for BackgroundScheduler module (Feature 64)."""

import time
import threading

import pytest
from src.core.background_scheduler import (
    BackgroundScheduler,
    ScheduledJob,
    SchedulerStats,
)


class TestSchedulerCore:
    """Test core scheduler functionality."""

    def test_register_job(self):
        scheduler = BackgroundScheduler(check_interval=1)

        @scheduler.register("test_job", interval_seconds=10)
        def my_job():
            return "done"

        job = scheduler.get_job("test_job")
        assert job is not None
        assert job.name == "test_job"
        assert job.interval_seconds == 10
        assert job.enabled is True

    def test_add_job(self):
        scheduler = BackgroundScheduler()

        def my_job():
            pass

        scheduler.add_job("direct_job", my_job, interval_seconds=30)
        job = scheduler.get_job("direct_job")
        assert job is not None
        assert job.interval_seconds == 30

    def test_remove_job(self):
        scheduler = BackgroundScheduler()

        @scheduler.register("removable", interval_seconds=10)
        def my_job():
            pass

        assert scheduler.get_job("removable") is not None
        result = scheduler.remove_job("removable")
        assert result is True
        assert scheduler.get_job("removable") is None

    def test_remove_nonexistent(self):
        scheduler = BackgroundScheduler()
        result = scheduler.remove_job("nonexistent")
        assert result is False

    def test_get_nonexistent_job(self):
        scheduler = BackgroundScheduler()
        assert scheduler.get_job("does_not_exist") is None


class TestSchedulerLifecycle:
    """Test scheduler start/stop."""

    def test_start_stop(self):
        scheduler = BackgroundScheduler()
        scheduler.start()
        assert scheduler.get_stats().is_running is True
        scheduler.stop()
        assert scheduler.get_stats().is_running is False

    def test_double_start_is_safe(self):
        scheduler = BackgroundScheduler()
        scheduler.start()
        scheduler.start()  # Should be no-op
        scheduler.stop()

    def test_stop_without_start(self):
        scheduler = BackgroundScheduler()
        scheduler.stop()  # Should not raise


class TestJobExecution:
    """Test job execution mechanics."""

    def test_run_on_start(self):
        scheduler = BackgroundScheduler(check_interval=0.5)
        results = []

        @scheduler.register("run_now", interval_seconds=3600, run_on_start=True)
        def my_job():
            results.append("ran")

        scheduler.start()
        time.sleep(1)
        scheduler.stop()

        # The job should have run at least once on start
        assert len(results) >= 1

    def test_job_error_handling(self):
        scheduler = BackgroundScheduler(check_interval=0.5)

        @scheduler.register("failing", interval_seconds=1, run_on_start=True)
        def failing_job():
            raise ValueError("Test error")

        scheduler.start()
        time.sleep(1.5)
        scheduler.stop()

        job = scheduler.get_job("failing")
        assert job is not None
        assert job.total_errors > 0


class TestSchedulerStats:
    """Test scheduler statistics."""

    def test_empty_stats(self):
        scheduler = BackgroundScheduler()
        stats = scheduler.get_stats()
        assert isinstance(stats, SchedulerStats)
        assert stats.total_jobs == 0
        assert stats.active_jobs == 0
        assert stats.is_running is False

    def test_stats_with_jobs(self):
        scheduler = BackgroundScheduler()

        @scheduler.register("job1", interval_seconds=10)
        def job1():
            pass

        @scheduler.register("job2", interval_seconds=20)
        def job2():
            pass

        stats = scheduler.get_stats()
        assert stats.total_jobs == 2
        assert stats.active_jobs == 2
        assert len(stats.jobs) == 2

    def test_disabled_job_not_active(self):
        scheduler = BackgroundScheduler()

        @scheduler.register("disabled_job", interval_seconds=10)
        def my_job():
            pass

        job = scheduler.get_job("disabled_job")
        job.enabled = False

        stats = scheduler.get_stats()
        assert stats.active_jobs == 0
