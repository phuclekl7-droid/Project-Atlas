"""
Calendar Sync (Feature #92).
Integrates with Google Calendar API to read and manage events.

Provides:
- List today's events
- List upcoming events (configurable days)
- Create events
- Simple text-based calendar view

Usage:
    CalendarPlugin.execute("today")  # Today's events
    CalendarPlugin.execute("upcoming 3")  # Next 3 days
    CalendarPlugin.execute("add Meeting at 3pm")
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("calendar")

try:
    import requests as req_lib
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


@dataclass
class CalendarEvent:
    """A calendar event."""
    id: str = ""
    summary: str = ""
    description: str = ""
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    attendees: list[str] = field(default_factory=list)
    is_all_day: bool = False

    @property
    def time_range(self) -> str:
        """Get formatted time range."""
        if self.is_all_day:
            return "All day"
        return f"{self.start_time} → {self.end_time}"


def _get_api_key() -> Optional[str]:
    """Get Google Calendar API key from environment."""
    return os.environ.get("GOOGLE_CALENDAR_API_KEY")


def _get_calendar_id() -> str:
    """Get calendar ID (default: primary)."""
    return os.environ.get("GOOGLE_CALENDAR_ID", "primary")


def _fetch_events(
    api_key: str,
    calendar_id: str = "primary",
    days: int = 1,
    max_results: int = 20,
) -> list[CalendarEvent]:
    """
    Fetch events from Google Calendar API.

    Uses the public Google Calendar API v3 with API key.
    For private calendars, OAuth 2.0 would be needed.
    """
    if not _HAS_REQUESTS:
        logger.warning("requests not installed")
        return []

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days)).isoformat() + "Z"

    try:
        url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
        params = {
            "key": api_key,
            "timeMin": time_min,
            "timeMax": time_max,
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        resp = req_lib.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            events = []
            for item in data.get("items", []):
                start_info = item.get("start", {})
                end_info = item.get("end", {})

                is_all_day = "date" in start_info and "dateTime" not in start_info

                event = CalendarEvent(
                    id=item.get("id", ""),
                    summary=item.get("summary", "(No title)"),
                    description=item.get("description", ""),
                    start_time=start_info.get("dateTime", start_info.get("date", "")),
                    end_time=end_info.get("dateTime", end_info.get("date", "")),
                    location=item.get("location", ""),
                    attendees=[a.get("email", "") for a in item.get("attendees", [])],
                    is_all_day=is_all_day,
                )
                events.append(event)
            return events
        elif resp.status_code == 403:
            logger.warning("Calendar API access forbidden (public calendar required with API key)")
            return []
        else:
            logger.warning(f"Google Calendar API error: {resp.status_code}")
            return []
    except Exception as e:
        logger.warning(f"Calendar API request failed: {e}")
        return []


def _parse_natural_language(text: str) -> Optional[dict]:
    """Parse natural language into event creation data."""
    # Try patterns like "Meeting at 3pm tomorrow" or "add event: title"
    patterns = [
        r'(?:add|create|new)\s+(?:event|meeting|appointment)\s*[:=]?\s*(.+?)(?:\s+at\s+|\s+on\s+)(.+?)(?:$| for | lasting )',
        r'(?:add|create|new)\s+(?:event|meeting|appointment)\s*[:=]?\s*(.+?)(?:$| tomorrow| today)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                "summary": match.group(1).strip(),
                "time_hint": match.group(2).strip() if match.lastindex and match.lastindex >= 2 else "",
            }

    # Simple format: "title: value"
    if ":" in text:
        parts = text.split(":", 1)
        return {"summary": parts[0].strip(), "description": parts[1].strip()}

    return None


def _format_events(events: list[CalendarEvent], title: str = "📅 Calendar") -> str:
    """Format calendar events as Markdown."""
    if not events:
        return f"## {title}\\n\\n*No upcoming events.* ✅"

    lines = [f"## {title}", ""]
    for i, event in enumerate(events, 1):
        lines.append(f"### {i}. {event.summary}")
        lines.append(f"- **Time:** {event.time_range}")
        if event.location:
            lines.append(f"- **Location:** {event.location}")
        if event.description:
            desc = event.description[:200]
            lines.append(f"- **Details:** {desc}")
        lines.append("")

    return "\n".join(lines)


class CalendarPlugin(BasePlugin):
    """
    Syncs with Google Calendar to read and manage events.

    Commands:
    - "today": Events for today
    - "upcoming [N]": Events for next N days (default 7)
    - "week": Events for this week
    - "add <summary> at <time>": Create event (simple format)
    - "help": Show help

    Setup:
    1. Get a Google Calendar API key from Google Cloud Console
    2. Set GOOGLE_CALENDAR_API_KEY env var
    3. Make sure your calendar is set to 'Public' or use OAuth 2.0

    Examples:
        "today"
        "upcoming 3"
        "week"
        "Team standup at 10am"
    """

    name = "calendar"
    description = "Đồng bộ lịch Google Calendar"

    def execute(self, input_str: str) -> PluginResult:
        """Execute calendar command."""
        text = input_str.strip()
        if not text:
            return self._show_help()

        api_key = _get_api_key()
        if not api_key:
            return PluginResult(
                success=False,
                error=(
                    "❌ **Chưa cấu hình Google Calendar API.**\\n\\n"
                    "1. Truy cập https://console.cloud.google.com\\n"
                    "2. Tạo project → Bật Google Calendar API\\n"
                    "3. Tạo API key \\n"
                    "4. Set: `GOOGLE_CALENDAR_API_KEY=...`\\n"
                    "5. Calendar phải ở chế độ Public (hoặc dùng OAuth)"
                )
            )

        cmd = text.lower()
        cal_id = _get_calendar_id()

        if cmd in ("today", "day"):
            events = _fetch_events(api_key, cal_id, days=1)
            output = _format_events(events, "📅 Today's Events")
            return PluginResult(success=True, output=output)

        elif cmd.startswith("upcoming"):
            parts = cmd.split()
            days = 7
            if len(parts) > 1:
                try:
                    days = int(parts[1])
                except ValueError:
                    pass
            events = _fetch_events(api_key, cal_id, days=days)
            output = _format_events(events, f"📅 Upcoming {days} Days")
            return PluginResult(success=True, output=output)

        elif cmd == "week":
            events = _fetch_events(api_key, cal_id, days=7)
            output = _format_events(events, "📅 This Week")
            return PluginResult(success=True, output=output)

        elif cmd.startswith("add "):
            parsed = _parse_natural_language(text[4:].strip())
            if parsed:
                return PluginResult(
                    success=True,
                    output=(
                        f"📝 **Event Preview**\\n\\n"
                        f"- **Title:** {parsed.get('summary', 'N/A')}\\n"
                        f"- **Description:** {parsed.get('description', '(none)')}\\n\\n"
                        f"⚠️ Google Calendar API write requires OAuth 2.0.\\n"
                        f"Use the Google Cloud Console or a third-party tool to create events."
                    )
                )
            return PluginResult(
                success=False,
                error="Không thể phân tích thông tin sự kiện.\\nVí dụ: `add Team Meeting at 3pm tomorrow`"
            )

        elif cmd in ("help", ""):
            return self._show_help()
        else:
            return PluginResult(
                success=False,
                error=f"Lệnh không hợp lệ: `{text}`\\n\\nLệnh: today, upcoming [N], week, add, help"
            )

    def _show_help(self) -> PluginResult:
        """Show help message."""
        return PluginResult(
            success=True,
            output=(
                "## 📅 Calendar Commands\\n\\n"
                "| Command | Description |\\n"
                "|:--------|:------------|\\n"
                "| `today` | Today's events |\\n"
                "| `upcoming [N]` | Next N days (default 7) |\\n"
                "| `week` | This week's events |\\n"
                "| `add <title> at <time>` | Create event (preview only) |\\n"
                "| `help` | Show this help |\\n\\n"
                "**Setup:**\\n"
                "1. `GOOGLE_CALENDAR_API_KEY` env var\\n"
                "2. Calendar must be Public for API key access"
            )
        )
