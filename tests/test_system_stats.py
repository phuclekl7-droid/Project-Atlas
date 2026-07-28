"""
Unit tests for System Resource Indicator.

Tests:
- SystemStats dataclass defaults
- get_system_stats() without psutil
- get_system_stats() with mocked psutil (success)
- get_system_stats() with psutil error
- render_stats_html() formatting
- render_cpu_bar() formatting
- Color coding by threshold
- Fallback when psutil unavailable
"""

from unittest.mock import MagicMock, patch

import pytest

from src.features.system_stats import (
    SystemStats,
    get_system_stats,
    render_stats_html,
    render_cpu_bar,
    _HAS_PSUTIL,
)


class TestSystemStatsDataclass:
    def test_default_values(self):
        stats = SystemStats()
        assert stats.cpu_percent == 0.0
        assert stats.memory_percent == 0.0
        assert stats.memory_used_gb == 0.0
        assert stats.memory_total_gb == 0.0
        assert stats.available is False
        assert stats.error == ""

    def test_with_values(self):
        stats = SystemStats(
            cpu_percent=45.5,
            memory_percent=62.3,
            memory_used_gb=8.2,
            memory_total_gb=16.0,
            available=True,
        )
        assert stats.cpu_percent == 45.5
        assert stats.memory_percent == 62.3
        assert stats.memory_used_gb == 8.2
        assert stats.memory_total_gb == 16.0
        assert stats.available is True


class TestGetSystemStats:
    def test_psutil_not_available(self, monkeypatch):
        """Without psutil, should return unavailable stats."""
        monkeypatch.setattr("src.features.system_stats._HAS_PSUTIL", False)
        stats = get_system_stats()
        assert stats.available is False
        assert "psutil" in stats.error

    def test_psutil_available_success(self, monkeypatch):
        """With psutil, should return actual stats."""
        # Mock psutil
        mock_mem = MagicMock()
        mock_mem.percent = 45.0
        mock_mem.used = 8 * 1024**3  # 8 GB
        mock_mem.total = 16 * 1024**3  # 16 GB

        monkeypatch.setattr("src.features.system_stats._HAS_PSUTIL", True)
        monkeypatch.setattr("src.features.system_stats.psutil.cpu_percent", lambda interval: 35.0)
        monkeypatch.setattr("src.features.system_stats.psutil.virtual_memory", lambda: mock_mem)

        stats = get_system_stats()
        assert stats.available is True
        assert stats.cpu_percent == 35.0
        assert stats.memory_percent == 45.0
        assert stats.memory_used_gb == 8.0
        assert stats.memory_total_gb == 16.0

    def test_psutil_error(self, monkeypatch):
        """If psutil raises, should return unavailable with error."""
        monkeypatch.setattr("src.features.system_stats._HAS_PSUTIL", True)

        def mock_error():
            raise RuntimeError("Access denied")

        monkeypatch.setattr("src.features.system_stats.psutil.cpu_percent", mock_error)

        stats = get_system_stats()
        assert stats.available is False
        assert len(stats.error) > 0


class TestRenderStatsHtml:
    def test_unavailable_returns_empty(self):
        """Unavailable stats should return empty string."""
        stats = SystemStats()
        html = render_stats_html(stats)
        assert html == ""

    def test_render_available_stats(self):
        """Available stats should render HTML with CPU and RAM."""
        stats = SystemStats(
            cpu_percent=35.0,
            memory_percent=50.0,
            memory_used_gb=8.0,
            memory_total_gb=16.0,
            available=True,
        )
        html = render_stats_html(stats)
        assert "CPU" in html
        assert "RAM" in html
        assert "35" in html
        assert "8.0" in html
        assert "16" in html

    def test_cpu_low_color(self):
        """Low CPU (<30%) should use green color."""
        stats = SystemStats(cpu_percent=15.0, memory_percent=30.0, available=True)
        html = render_stats_html(stats)
        assert "#4ecdc4" in html

    def test_cpu_medium_color(self):
        """Medium CPU (30-70%) should use yellow."""
        stats = SystemStats(cpu_percent=50.0, memory_percent=30.0, available=True)
        html = render_stats_html(stats)
        assert "#ffd700" in html

    def test_cpu_high_color(self):
        """High CPU (>70%) should use red."""
        stats = SystemStats(cpu_percent=85.0, memory_percent=30.0, available=True)
        html = render_stats_html(stats)
        assert "#ff6b6b" in html

    def test_memory_low_color(self):
        """Low RAM (<50%) should use green."""
        stats = SystemStats(cpu_percent=20.0, memory_percent=30.0, available=True)
        html = render_stats_html(stats)
        assert "#4ecdc4" in html

    def test_memory_high_color(self):
        """High RAM (>80%) should use red."""
        stats = SystemStats(cpu_percent=20.0, memory_percent=85.0, available=True)
        html = render_stats_html(stats)
        assert "#ff6b6b" in html


class TestRenderCpuBar:
    def test_unavailable_returns_empty(self):
        html = render_cpu_bar(SystemStats())
        assert html == ""

    def test_render_bar(self):
        """Should render a CPU bar with percentage."""
        stats = SystemStats(cpu_percent=42.0, available=True)
        html = render_cpu_bar(stats)
        assert "CPU" in html
        assert "42" in html
        assert "%" in html
        assert "width" in html.lower()

    def test_bar_width_matches_percent(self):
        """The bar width style should match CPU percentage."""
        stats = SystemStats(cpu_percent=75.0, available=True)
        html = render_cpu_bar(stats)
        assert "75%" in html or "width:75" in html

    def test_bar_color_high(self):
        """High CPU bar should use red."""
        stats = SystemStats(cpu_percent=90.0, available=True)
        html = render_cpu_bar(stats)
        assert "#ff6b6b" in html
