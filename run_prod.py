"""
Production runner for Project Atlas (Feature 8)

Wraps the Streamlit app with Gunicorn/Uvicorn for production deployment.

Usage:
    # Via Gunicorn (recommended for production):
    gunicorn -c gunicorn_config.py run_prod:app

    # Direct Uvicorn:
    uvicorn run_prod:app --host 0.0.0.0 --port 8501 --workers 4

    # Streamlit native (development):
    streamlit run app.py
"""

import os
import sys

# ── Production Settings ──
os.environ.setdefault("STREAMLIT_SERVER_PORT", "8501")
os.environ.setdefault("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
os.environ.setdefault("STREAMLIT_THEME_BASE", "dark")

# ── ASGI App ──
# Streamlit does not natively support ASGI wrapping.
# For production, use the streamlit CLI or gunicorn with a subprocess.
# This file provides the ASGI interface for monitoring/health checks.

from typing import Any, Callable


async def app(scope: dict, receive: Callable, send: Callable) -> None:
    """Minimal ASGI app for health checks and monitoring.

    For actual Streamlit serving, use:
        streamlit run app.py --server.port 8501 --server.address 0.0.0.0

    Or in Docker:
        ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
    """
    if scope["type"] == "http":
        path = scope.get("path", "")
        if path == "/health":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"status":"healthy","service":"project-atlas","version":"0.7.0"}',
            })
        elif path == "/":
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/html"),
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b"<h1>Project Atlas</h1><p>Running. Use Streamlit port 8501 for the UI.</p>",
            })
        else:
            await send({
                "type": "http.response.start",
                "status": 404,
                "headers": [(b"content-type", b"text/plain")],
            })
            await send({
                "type": "http.response.body",
                "body": b"Not Found",
            })
    else:
        await send({
            "type": "http.response.start",
            "status": 400,
            "headers": [(b"content-type", b"text/plain")],
        })
        await send({
            "type": "http.response.body",
            "body": b"Bad Request",
        })


if __name__ == "__main__":
    """When run directly, start Streamlit as a subprocess."""
    import subprocess
    import sys

    print("Starting Project Atlas in production mode...")
    port = os.environ["STREAMLIT_SERVER_PORT"]
    address = os.environ["STREAMLIT_SERVER_ADDRESS"]

    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", port,
        "--server.address", address,
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(cmd)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait()
