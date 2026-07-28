"""
Gunicorn configuration for Project Atlas (Feature 8)

This file configures Gunicorn to serve the Streamlit app via Uvicorn
for production deployment.

Usage:
    gunicorn -c gunicorn_config.py app:app
    # Or with Uvicorn workers for ASGI:
    gunicorn -c gunicorn_config.py --worker-class uvicorn.workers.UvicornWorker app:app

For Streamlit, use the run_prod.py wrapper instead:
    python run_prod.py
"""

import multiprocessing
import os

# ── Server Socket ──
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8501")
backlog = int(os.getenv("GUNICORN_BACKLOG", "2048"))

# ── Worker Processes ──
# Recommended: (2 * CPU cores) + 1
workers = int(os.getenv("GUNICORN_WORKERS", str(multiprocessing.cpu_count() * 2 + 1)))
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "sync")
threads = int(os.getenv("GUNICORN_THREADS", "4"))
worker_connections = int(os.getenv("GUNICORN_WORKER_CONNECTIONS", "1000"))

# ── Timeouts ──
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))  # seconds
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))

# ── Logging ──
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")  # stdout
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")     # stderr
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# ── Process Name ──
proc_name = os.getenv("GUNICORN_PROC_NAME", "project-atlas")

# ── Security ──
limit_request_line = int(os.getenv("GUNICORN_LIMIT_REQUEST_LINE", "4094"))
limit_request_fields = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELDS", "100"))
limit_request_field_size = int(os.getenv("GUNICORN_LIMIT_REQUEST_FIELD_SIZE", "8190"))

# ── SSL (optional) ──
# keyfile = os.getenv("SSL_KEY_FILE")
# certfile = os.getenv("SSL_CERT_FILE")

# ── Preload App ──
preload_app = os.getenv("GUNICORN_PRELOAD", "true").lower() == "true"

# ── Graceful Reload ──
reload = os.getenv("GUNICORN_RELOAD", "false").lower() == "true"
reload_engine = os.getenv("GUNICORN_RELOAD_ENGINE", "auto")


def post_fork(server, worker):
    """Log worker startup."""
    server.log.info(f"Worker spawned (pid: {worker.pid})")


def pre_fork(server, worker):
    """Log worker pre-fork."""
    pass


def when_ready(server):
    """Log server readiness."""
    server.log.info(
        f"Project Atlas: ready on {bind} "
        f"({workers} workers, {threads} threads per worker)"
    )


def on_exit(server):
    """Log server shutdown."""
    server.log.info("Project Atlas: shutting down")
