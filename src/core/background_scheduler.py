"""
Scheduled Background Tasks Module (Feature 64)

Provides a lightweight background task scheduler for periodic operations
such as session summarization, data cleanup, and knowledge consolidation.

Uses a background thread with a simple job queue. Does NOT require APScheduler
as a dependency — uses Python's built-in threading + time module with a
simple scheduler loop. If APScheduler is available, it can be used optionally.

Usage:
    from src.core.background_scheduler import BackgroundScheduler, scheduled_job

    scheduler = BackgroundScheduler()

    @scheduler.register("daily_cleanup", interval_hours=24)
    def cleanup_old_data():
        print("Cleaning up...")

    scheduler.start()
    # ...
    scheduler.stop()
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.core import setup_logger

logger = setup_logger("bg_scheduler")


# ============================================================
# Data Models
# ============================================================


@dataclass
class ScheduledJob:
    """Represents a single scheduled task.

    Attributes:
        name: Unique name for this job
        func: Callable to execute
        interval_seconds: How often to run (in seconds)
        run_on_start: Whether to run immediately on start
        last_run: Timestamp of last execution (None if never run)
        total_runs: Number of times executed
        total_errors: Number of execution errors
        enabled: Whether this job is active
    """

    name: str
    func: Callable[[], Any]
    interval_seconds: float
    run_on_start: bool = False
    last_run: Optional[float] = None
    total_runs: int = 0
    total_errors: int = 0
    enabled: bool = True


@dataclass
class SchedulerStats:
    """Statistics for the scheduler and its jobs."""

    is_running: bool = False
    total_jobs: int = 0
    active_jobs: int = 0
    uptime_seconds: float = 0.0
    jobs: list[dict] = field(default_factory=list)


# ============================================================
# Background Scheduler
# ============================================================


class BackgroundScheduler:
    """Lightweight background task scheduler using a daemon thread.

    Thread-safe: uses a lock when modifying the job list.

    Usage:
        scheduler = BackgroundScheduler()

        @scheduler.register("summarize", interval_minutes=60)
        def auto_summarize():
            workflow.summarize_session("main")

        scheduler.start()  # Start background thread
        # ... app runs normally ...
        scheduler.stop()   # On shutdown
    """

    def __init__(self, check_interval: float = 5.0):
        """Initialize the scheduler.

        Args:
            check_interval: How often (seconds) to check for due jobs
        """
        self._jobs: list[ScheduledJob] = []
        self._lock = threading.Lock()
        self._check_interval = check_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_time: Optional[float] = None

    # ── Public API ──

    def register(
        self,
        name: str,
        interval_minutes: Optional[float] = None,
        interval_seconds: Optional[float] = None,
        interval_hours: Optional[float] = None,
        run_on_start: bool = False,
    ) -> Callable:
        """Decorator to register a function as a scheduled job.

        Args:
            name: Unique job name
            interval_minutes: Run every N minutes
            interval_seconds: Run every N seconds (overrides interval_minutes)
            interval_hours: Run every N hours (overrides interval_minutes)
            run_on_start: Whether to run immediately when scheduler starts

        Returns:
            Decorator function

        Usage:
            @scheduler.register("cleanup", interval_hours=24)
            def cleanup():
                pass
        """
        # Calculate interval in seconds
        if interval_seconds is not None:
            interval = interval_seconds
        elif interval_hours is not None:
            interval = interval_hours * 3600
        elif interval_minutes is not None:
            interval = interval_minutes * 60
        else:
            interval = 300  # Default: 5 minutes

        def decorator(func: Callable) -> Callable:
            job = ScheduledJob(
                name=name,
                func=func,
                interval_seconds=interval,
                run_on_start=run_on_start,
            )
            with self._lock:
                # Replace existing job with same name
                for i, existing in enumerate(self._jobs):
                    if existing.name == name:
                        self._jobs[i] = job
                        break
                else:
                    self._jobs.append(job)
            logger.info(
                f"Registered job '{name}' (interval={interval}s, "
                f"run_on_start={run_on_start})"
            )
            return func

        return decorator

    def add_job(
        self,
        name: str,
        func: Callable,
        interval_seconds: float = 300,
        run_on_start: bool = False,
    ) -> None:
        """Add a job directly (non-decorator form).

        Args:
            name: Unique job name
            func: Callable to execute
            interval_seconds: Interval in seconds
            run_on_start: Run immediately on start
        """
        job = ScheduledJob(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            run_on_start=run_on_start,
        )
        with self._lock:
            self._jobs.append(job)
        logger.info(f"Added job '{name}' (interval={interval_seconds}s)")

    def remove_job(self, name: str) -> bool:
        """Remove a job by name.

        Args:
            name: Job name to remove

        Returns:
            True if job was found and removed
        """
        with self._lock:
            for i, job in enumerate(self._jobs):
                if job.name == name:
                    self._jobs.pop(i)
                    logger.info(f"Removed job '{name}'")
                    return True
        return False

    def start(self) -> None:
        """Start the scheduler background thread.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._thread and self._thread.is_alive():
            logger.debug("Scheduler already running")
            return

        self._stop_event.clear()
        self._start_time = time.time()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="bg-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"Background scheduler started "
            f"({len(self._jobs)} jobs, check_interval={self._check_interval}s)"
        )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the scheduler gracefully.

        Args:
            timeout: Max seconds to wait for the thread to stop
        """
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Scheduler thread did not stop within timeout")
            else:
                logger.info("Background scheduler stopped")
        self._thread = None

    def get_job(self, name: str) -> Optional[ScheduledJob]:
        """Get a job by name.

        Args:
            name: Job name

        Returns:
            ScheduledJob or None
        """
        with self._lock:
            for job in self._jobs:
                if job.name == name:
                    return job
        return None

    def get_stats(self) -> SchedulerStats:
        """Get scheduler statistics.

        Returns:
            SchedulerStats with job details
        """
        with self._lock:
            active = sum(1 for j in self._jobs if j.enabled)
            uptime = 0.0
            if self._start_time:
                uptime = time.time() - self._start_time

            jobs_info = []
            for job in self._jobs:
                jobs_info.append({
                    "name": job.name,
                    "interval_seconds": job.interval_seconds,
                    "enabled": job.enabled,
                    "total_runs": job.total_runs,
                    "total_errors": job.total_errors,
                    "last_run": job.last_run,
                    "next_run": (
                        job.last_run + job.interval_seconds
                        if job.last_run
                        else time.time()
                    ),
                })

            return SchedulerStats(
                is_running=self._thread is not None and self._thread.is_alive(),
                total_jobs=len(self._jobs),
                active_jobs=active,
                uptime_seconds=uptime,
                jobs=jobs_info,
            )

    # ── Internal ──

    def _run_loop(self) -> None:
        """Main scheduler loop runs in background thread."""
        logger.debug("Scheduler loop started")

        while not self._stop_event.is_set():
            try:
                self._check_and_run_jobs()
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")

            self._stop_event.wait(self._check_interval)

        logger.debug("Scheduler loop ended")

    def _check_and_run_jobs(self) -> None:
        """Check all jobs and run any that are due."""
        now = time.time()

        with self._lock:
            for job in self._jobs:
                if not job.enabled:
                    continue

                # Check if job is due
                should_run = False

                if job.last_run is None:
                    # Never run — check run_on_start
                    should_run = job.run_on_start
                    # After first check, set last_run to now so it doesn't run again immediately
                    if not should_run:
                        job.last_run = now
                else:
                    elapsed = now - job.last_run
                    should_run = elapsed >= job.interval_seconds

                if should_run:
                    # Run job (release lock during execution)
                    job.last_run = now
                    self._execute_job(job)

    def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a single job, handling errors gracefully.

        Args:
            job: The job to execute
        """
        try:
            logger.debug(f"Running job '{job.name}'")
            result = job.func()
            job.total_runs += 1

            # Log result if it's a string
            if isinstance(result, str):
                logger.info(f"Job '{job.name}': {result}")
            elif isinstance(result, dict):
                logger.info(f"Job '{job.name}': completed with {len(result)} fields")

        except Exception as e:
            job.total_errors += 1
            logger.error(f"Job '{job.name}' failed: {e}", exc_info=True)


# ============================================================
# Module-level convenience
# ============================================================

# Global scheduler instance (singleton pattern)
_default_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance.

    Usage:
        scheduler = get_scheduler()
        scheduler.start()
    """
    global _default_scheduler
    if _default_scheduler is None:
        _default_scheduler = BackgroundScheduler()
    return _default_scheduler


def register_job(
    name: str,
    interval_minutes: Optional[float] = None,
    interval_hours: Optional[float] = None,
) -> Callable:
    """Decorator to register a job on the global scheduler.

    Usage:
        @register_job("cleanup", interval_hours=24)
        def cleanup():
            pass
    """
    scheduler = get_scheduler()
    return scheduler.register(
        name,
        interval_minutes=interval_minutes,
        interval_hours=interval_hours,
    )
