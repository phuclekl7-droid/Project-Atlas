"""
Tests for Feature #82: Prometheus Metrics Exporter.
"""

import pytest

from src.core.metrics_exporter import MetricsExporter


class TestMetricsExporter:
    def test_initialization(self):
        exporter = MetricsExporter()
        stats = exporter.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_model_calls"] == 0

    def test_increment_requests(self):
        exporter = MetricsExporter()
        exporter.increment_requests(endpoint="chat")
        exporter.increment_requests(endpoint="chat")
        exporter.increment_requests(endpoint="search")
        stats = exporter.get_stats()
        assert stats["total_requests"] == 3

    def test_increment_model_calls(self):
        exporter = MetricsExporter()
        exporter.increment_model_calls(provider="openai")
        exporter.increment_model_calls(provider="ollama", count=3)
        stats = exporter.get_stats()
        assert stats["total_model_calls"] == 4

    def test_increment_errors(self):
        exporter = MetricsExporter()
        exporter.increment_errors(error_type="api_error")
        exporter.increment_errors(error_type="timeout")
        stats = exporter.get_stats()
        assert stats["total_errors"] == 2

    def test_increment_plugin_calls(self):
        exporter = MetricsExporter()
        exporter.increment_plugin_calls(plugin_name="web_search")
        stats = exporter.get_stats()
        assert stats["total_model_calls"] >= 0  # Just checking no crash

    def test_record_latency(self):
        exporter = MetricsExporter()
        exporter.record_latency("chat", 1.5)
        exporter.record_latency("chat", 2.0)
        exporter.record_latency("chat", 0.5)
        # Check prometheus output has latency data
        prom = exporter.format_prometheus()
        assert "latency" in prom

    def test_set_active_sessions(self):
        exporter = MetricsExporter()
        exporter.set_active_sessions(5)
        prom = exporter.format_prometheus()
        assert "active_sessions 5" in prom

    def test_set_knowledge_chunks(self):
        exporter = MetricsExporter()
        exporter.set_knowledge_chunks(100)
        prom = exporter.format_prometheus()
        assert "knowledge_chunks 100" in prom

    def test_cache_tracking(self):
        exporter = MetricsExporter()
        exporter.record_cache_result(hit=True)
        exporter.record_cache_result(hit=True)
        exporter.record_cache_result(hit=False)
        prom = exporter.format_prometheus()
        assert "cache_hits_total 2" in prom
        assert "cache_misses_total 1" in prom

    def test_format_prometheus(self):
        exporter = MetricsExporter()
        exporter.increment_requests("test_endpoint")
        prom = exporter.format_prometheus()
        assert "TYPE" in prom
        assert "HELP" in prom
        assert "test_endpoint" in prom

    def test_format_json(self):
        exporter = MetricsExporter()
        exporter.increment_requests("chat")
        json_data = exporter.format_json()
        assert "requests" in json_data
        assert json_data["requests"]["chat"] == 1

    def test_get_stats(self):
        exporter = MetricsExporter()
        exporter.increment_requests("chat")
        exporter.set_active_sessions(3)
        stats = exporter.get_stats()
        assert stats["total_requests"] == 1
        assert stats["active_sessions"] == 3
        assert "uptime_seconds" in stats

    def test_uptime_increasing(self):
        import time
        exporter = MetricsExporter()
        stats1 = exporter.get_stats()
        time.sleep(0.01)
        stats2 = exporter.get_stats()
        assert stats2["uptime_seconds"] > stats1["uptime_seconds"]
