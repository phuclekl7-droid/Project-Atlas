"""
Prometheus Metrics Exporter (Feature #82).
Exposes application metrics for Prometheus scraping.

Provides:
- Request counters by endpoint
- Request latency histogram
- Model call counters by provider
- Error counters by type
- Active session gauge
- Memory usage gauge

Usage:
    exporter = MetricsExporter()
    exporter.increment_requests(endpoint="send_message")
    exporter.record_latency(endpoint="generate", seconds=1.5)
    metrics_text = exporter.format_prometheus()
    # For Grafana: configure Prometheus to scrape /metrics endpoint
"""

import json
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger

logger = setup_logger("metrics")


class MetricsExporter:
    """
    Collects and exports application metrics in Prometheus text format.

    No external dependencies — pure Python implementation.
    Metrics can be exposed via a FastAPI /metrics endpoint or logged.

    Usage:
        exporter = MetricsExporter()

        # Record metrics
        exporter.increment_requests(endpoint="chat")
        exporter.increment_model_calls(provider="openai")
        exporter.record_latency("chat", 1.5)
        exporter.set_active_sessions(5)
        exporter.increment_errors("api_error")

        # Export as Prometheus text
        prometheus_text = exporter.format_prometheus()
        # Serve via FastAPI /metrics endpoint
    """

    def __init__(self, app_name: str = "project_atlas"):
        self._app_name = app_name
        self._start_time = time.time()
        self._lock = threading.Lock()

        # Counters
        self._request_count: dict[str, int] = defaultdict(int)
        self._model_call_count: dict[str, int] = defaultdict(int)
        self._error_count: dict[str, int] = defaultdict(int)
        self._plugin_call_count: dict[str, int] = defaultdict(int)

        # Latency tracking (endpoint -> list of seconds)
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._model_latencies: dict[str, list[float]] = defaultdict(list)

        # Gauges
        self._active_sessions = 0
        self._active_connections = 0
        self._knowledge_chunks = 0
        self._memory_usage_mb = 0.0

        # Cache hits/misses
        self._cache_hits = 0
        self._cache_misses = 0

    # ── Request Tracking ──

    def increment_requests(self, endpoint: str, count: int = 1) -> None:
        """Increment the request counter for an endpoint."""
        with self._lock:
            self._request_count[endpoint] += count

    def increment_model_calls(self, provider: str, count: int = 1) -> None:
        """Increment the model call counter for a provider."""
        with self._lock:
            self._model_call_count[provider] += count

    def increment_errors(self, error_type: str, count: int = 1) -> None:
        """Increment the error counter by type."""
        with self._lock:
            self._error_count[error_type] += count

    def increment_plugin_calls(self, plugin_name: str, count: int = 1) -> None:
        """Increment the plugin call counter."""
        with self._lock:
            self._plugin_call_count[plugin_name] += count

    # ── Latency Tracking ──

    def record_latency(self, endpoint: str, seconds: float) -> None:
        """Record a latency measurement for an endpoint."""
        with self._lock:
            self._latencies[endpoint].append(seconds)
            # Keep only last 1000 measurements
            if len(self._latencies[endpoint]) > 1000:
                self._latencies[endpoint] = self._latencies[endpoint][-1000:]

    def record_model_latency(self, provider: str, seconds: float) -> None:
        """Record a model call latency."""
        with self._lock:
            self._model_latencies[provider].append(seconds)
            if len(self._model_latencies[provider]) > 1000:
                self._model_latencies[provider] = self._model_latencies[provider][-1000:]

    # ── Gauges ──

    def set_active_sessions(self, count: int) -> None:
        """Set the active session count."""
        with self._lock:
            self._active_sessions = max(0, count)

    def set_knowledge_chunks(self, count: int) -> None:
        """Set the number of knowledge base chunks."""
        with self._lock:
            self._knowledge_chunks = count

    def record_cache_result(self, hit: bool) -> None:
        """Record a cache hit or miss."""
        with self._lock:
            if hit:
                self._cache_hits += 1
            else:
                self._cache_misses += 1

    # ── Prometheus Format ──

    def format_prometheus(self) -> str:
        """
        Format all metrics in Prometheus text exposition format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        lines.append(f"# HELP {self._app_name}_requests_total Total requests by endpoint")
        lines.append(f"# TYPE {self._app_name}_requests_total counter")

        with self._lock:
            for endpoint, count in sorted(self._request_count.items()):
                lines.append(f'{self._app_name}_requests_total{{endpoint="{endpoint}"}} {count}')

            lines.append("")
            lines.append(f"# HELP {self._app_name}_model_calls_total Total model calls by provider")
            lines.append(f"# TYPE {self._app_name}_model_calls_total counter")
            for provider, count in sorted(self._model_call_count.items()):
                lines.append(f'{self._app_name}_model_calls_total{{provider="{provider}"}} {count}')

            lines.append("")
            lines.append(f"# HELP {self._app_name}_errors_total Total errors by type")
            lines.append(f"# TYPE {self._app_name}_errors_total counter")
            for err_type, count in sorted(self._error_count.items()):
                lines.append(f'{self._app_name}_errors_total{{error_type="{err_type}"}} {count}')

            lines.append("")
            lines.append(f"# HELP {self._app_name}_plugin_calls_total Total plugin calls")
            lines.append(f"# TYPE {self._app_name}_plugin_calls_total counter")
            for plugin, count in sorted(self._plugin_call_count.items()):
                lines.append(f'{self._app_name}_plugin_calls_total{{plugin="{plugin}"}} {count}')

            # Latency histograms (p50, p95, p99)
            lines.append("")
            lines.append(f"# HELP {self._app_name}_request_latency_seconds Request latency by endpoint")
            lines.append(f"# TYPE {self._app_name}_request_latency_seconds gauge")
            for endpoint, lats in sorted(self._latencies.items()):
                if lats:
                    sorted_lats = sorted(lats)
                    p50 = sorted_lats[len(sorted_lats) // 2]
                    p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
                    p99 = sorted_lats[int(len(sorted_lats) * 0.99)]
                    lines.append(f'{self._app_name}_request_latency_seconds{{endpoint="{endpoint}",quantile="0.5"}} {p50}')
                    lines.append(f'{self._app_name}_request_latency_seconds{{endpoint="{endpoint}",quantile="0.95"}} {p95}')
                    lines.append(f'{self._app_name}_request_latency_seconds{{endpoint="{endpoint}",quantile="0.99"}} {p99}')

            lines.append("")
            lines.append(f"# HELP {self._app_name}_model_latency_seconds Model latency by provider")
            lines.append(f"# TYPE {self._app_name}_model_latency_seconds gauge")
            for provider, lats in sorted(self._model_latencies.items()):
                if lats:
                    sorted_lats = sorted(lats)
                    p50 = sorted_lats[len(sorted_lats) // 2]
                    p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
                    lines.append(f'{self._app_name}_model_latency_seconds{{provider="{provider}",quantile="0.5"}} {p50}')
                    lines.append(f'{self._app_name}_model_latency_seconds{{provider="{provider}",quantile="0.95"}} {p95}')

            # Gauges
            lines.append("")
            lines.append(f"# HELP {self._app_name}_active_sessions Active session count")
            lines.append(f"# TYPE {self._app_name}_active_sessions gauge")
            lines.append(f"{self._app_name}_active_sessions {self._active_sessions}")

            lines.append("")
            lines.append(f"# HELP {self._app_name}_knowledge_chunks Knowledge base chunk count")
            lines.append(f"# TYPE {self._app_name}_knowledge_chunks gauge")
            lines.append(f"{self._app_name}_knowledge_chunks {self._knowledge_chunks}")

            # Cache metrics
            lines.append("")
            lines.append(f"# HELP {self._app_name}_cache_hits_total Cache hits")
            lines.append(f"# TYPE {self._app_name}_cache_hits_total counter")
            lines.append(f"{self._app_name}_cache_hits_total {self._cache_hits}")

            lines.append("")
            lines.append(f"# HELP {self._app_name}_cache_misses_total Cache misses")
            lines.append(f"# TYPE {self._app_name}_cache_misses_total counter")
            lines.append(f"{self._app_name}_cache_misses_total {self._cache_misses}")

            # Uptime
            lines.append("")
            lines.append(f"# HELP {self._app_name}_uptime_seconds Application uptime")
            lines.append(f"# TYPE {self._app_name}_uptime_seconds gauge")
            lines.append(f"{self._app_name}_uptime_seconds {time.time() - self._start_time}")

        return "\n".join(lines) + "\n"

    # ── JSON Format (for debugging / API) ──

    def format_json(self) -> dict:
        """Format metrics as JSON dict."""
        with self._lock:
            return {
                "requests": dict(self._request_count),
                "model_calls": dict(self._model_call_count),
                "errors": dict(self._error_count),
                "plugin_calls": dict(self._plugin_call_count),
                "active_sessions": self._active_sessions,
                "knowledge_chunks": self._knowledge_chunks,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }

    def get_stats(self) -> dict:
        """Get summary statistics."""
        with self._lock:
            return {
                "total_requests": sum(self._request_count.values()),
                "total_model_calls": sum(self._model_call_count.values()),
                "total_errors": sum(self._error_count.values()),
                "active_sessions": self._active_sessions,
                "uptime_seconds": round(time.time() - self._start_time, 1),
            }
