"""
System Resource Indicator (Feature: RAM/CPU Monitor)

Displays CPU and RAM usage of the local machine in the sidebar footer.

Uses psutil for cross-platform system stats with a graceful fallback
if psutil is not installed.

Usage:
    stats = get_system_stats()
    html = render_stats_html(stats)
"""

from dataclasses import dataclass, field
from typing import Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


@dataclass
class SystemStats:
    """System resource snapshot."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    available: bool = False
    error: str = ""


def get_system_stats() -> SystemStats:
    """
    Get current CPU and memory usage.

    Returns:
        SystemStats with current resource usage.
        If psutil is not available, returns stats with available=False
        and an error message.
    """
    if not _HAS_PSUTIL:
        return SystemStats(
            available=False,
            error="Thiếu thư viện psutil. Cài: pip install psutil",
        )

    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return SystemStats(
            cpu_percent=round(cpu, 1),
            memory_percent=round(mem.percent, 1),
            memory_used_gb=round(mem.used / (1024**3), 1),
            memory_total_gb=round(mem.total / (1024**3), 1),
            available=True,
        )
    except Exception as e:
        return SystemStats(
            available=False,
            error=str(e),
        )


def render_stats_html(stats: SystemStats) -> str:
    """
    Render system stats as a compact HTML bar for the sidebar.

    Args:
        stats: SystemStats object from get_system_stats()

    Returns:
        HTML string with CPU and RAM usage bars.
        Returns empty string if stats are unavailable.
    """
    if not stats.available:
        return ""

    # CPU color
    if stats.cpu_percent < 30:
        cpu_color = "#4ecdc4"
    elif stats.cpu_percent < 70:
        cpu_color = "#ffd700"
    else:
        cpu_color = "#ff6b6b"

    # RAM color
    if stats.memory_percent < 50:
        mem_color = "#4ecdc4"
    elif stats.memory_percent < 80:
        mem_color = "#ffd700"
    else:
        mem_color = "#ff6b6b"

    return (
        f'<div style="font-size:0.7rem;color:#888;padding:0.3rem 0;'
        f'border-top:1px solid rgba(128,128,128,0.1);margin-top:0.3rem;">'
        f'💻 <b>CPU</b> '
        f'<span style="color:{cpu_color};">{stats.cpu_percent:.0f}%</span>'
        f' &nbsp;|&nbsp; '
        f'<b>RAM</b> '
        f'<span style="color:{mem_color};">{stats.memory_used_gb:.1f}GB/{stats.memory_total_gb:.0f}GB</span>'
        f'</div>'
    )


def render_cpu_bar(stats: SystemStats) -> str:
    """
    Render a thin CPU usage bar.

    Args:
        stats: SystemStats object

    Returns:
        HTML string with a 100%-width bar showing CPU usage.
    """
    if not stats.available:
        return ""

    cpu = stats.cpu_percent
    if cpu < 30:
        color = "#4ecdc4"
    elif cpu < 70:
        color = "#ffd700"
    else:
        color = "#ff6b6b"

    return (
        f'<div style="display:flex;align-items:center;gap:0.3rem;font-size:0.65rem;color:#888;">'
        f'<span>CPU</span>'
        f'<div style="flex:1;height:4px;background:rgba(128,128,128,0.1);border-radius:2px;">'
        f'<div style="width:{cpu}%;height:100%;background:{color};border-radius:2px;"></div>'
        f'</div>'
        f'<span style="color:{color};">{cpu:.0f}%</span>'
        f'</div>'
    )
