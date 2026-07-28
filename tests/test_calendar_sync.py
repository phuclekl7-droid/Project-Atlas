"""
Unit tests for Calendar Sync Plugin.

Tests:
- CalendarEvent dataclass
- _get_api_key and _get_calendar_id
- _fetch_events with mocked Google Calendar API
- _parse_natural_language for event creation
- _format_events for Markdown formatting
- Plugin execution with commands: today, upcoming, week, add, help
- Plugin metadata
- Error handling (no API key, empty input)
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.calendar_sync import (
    CalendarPlugin,
    CalendarEvent,
    _get_api_key,
    _get_calendar_id,
    _fetch_events,
    _parse_natural_language,
    _format_events,
)


# ============================================================
# Data Model Tests
# ============================================================


class TestCalendarEvent:
    def test_default_values(self):
        event = CalendarEvent()
        assert event.id == ""
        assert event.summary == ""
        assert event.is_all_day is False

    def test_with_values(self):
        event = CalendarEvent(
            id="evt_123",
            summary="Team Meeting",
            start_time="10:00",
            end_time="11:00",
        )
        assert event.id == "evt_123"
        assert event.summary == "Team Meeting"

    def test_time_range_regular(self):
        event = CalendarEvent(start_time="10:00", end_time="11:00")
        assert "10:00" in event.time_range
        assert "11:00" in event.time_range

    def test_time_range_all_day(self):
        event = CalendarEvent(start_time="2024-01-01", end_time="2024-01-02", is_all_day=True)
        assert "All day" in event.time_range


# ============================================================
# API Key / Calendar ID Tests
# ============================================================


class TestGetApiKey:
    def test_no_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CALENDAR_API_KEY", raising=False)
        assert _get_api_key() is None

    def test_key_from_env(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", "test_calendar_key_123")
        assert _get_api_key() == "test_calendar_key_123"


class TestGetCalendarId:
    def test_default_primary(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CALENDAR_ID", raising=False)
        assert _get_calendar_id() == "primary"

    def test_custom_id(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CALENDAR_ID", "custom@group.calendar.google.com")
        assert _get_calendar_id() == "custom@group.calendar.google.com"


# ============================================================
# Fetch Events Tests (mocked)
# ============================================================


class TestFetchEvents:
    def test_successful_fetch(self):
        """Successful API call should return list of CalendarEvents."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Standup Meeting",
                    "start": {"dateTime": "2024-01-15T09:00:00Z"},
                    "end": {"dateTime": "2024-01-15T09:30:00Z"},
                    "location": "Room A",
                    "description": "Daily standup",
                },
                {
                    "id": "evt2",
                    "summary": "Lunch",
                    "start": {"date": "2024-01-15"},
                    "end": {"date": "2024-01-15"},
                },
            ]
        }

        with patch("src.plugins.calendar_sync.req_lib.get", return_value=mock_resp):
            events = _fetch_events("test_key")

        assert len(events) == 2
        assert events[0].summary == "Standup Meeting"
        assert events[0].location == "Room A"
        assert events[1].is_all_day is True
        assert events[1].summary == "Lunch"

    def test_empty_response(self):
        """API with no items should return empty list."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"items": []}

        with patch("src.plugins.calendar_sync.req_lib.get", return_value=mock_resp):
            events = _fetch_events("test_key")

        assert events == []

    def test_http_403(self):
        """403 should log warning and return empty."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403

        with patch("src.plugins.calendar_sync.req_lib.get", return_value=mock_resp):
            events = _fetch_events("test_key")

        assert events == []

    def test_http_error(self):
        """Other HTTP errors should return empty."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch("src.plugins.calendar_sync.req_lib.get", return_value=mock_resp):
            events = _fetch_events("test_key")

        assert events == []


# ============================================================
# Natural Language Parsing Tests
# ============================================================


class TestParseNaturalLanguage:
    def test_add_event_with_time(self):
        result = _parse_natural_language("add Team Meeting at 3pm tomorrow")
        assert result is not None
        assert "Team Meeting" in result.get("summary", "")

    def test_create_event(self):
        result = _parse_natural_language("create event for Friday planning")
        assert result is not None

    def test_title_description_format(self):
        """Title: description format."""
        result = _parse_natural_language("Meeting: Discuss Q2 results")
        assert result is not None
        assert result.get("summary", "") == "Meeting" or "Q2" in result.get("description", "")

    def test_plain_text_no_match(self):
        """Plain text without event keywords should return None."""
        result = _parse_natural_language("What's the weather like?")
        assert result is None


# ============================================================
# Event Formatting Tests
# ============================================================


class TestFormatEvents:
    def test_empty_events(self):
        output = _format_events([], "Test Title")
        assert "No upcoming" in output or "Không có" in output or "✅" in output

    def test_single_event(self):
        events = [CalendarEvent(summary="Meeting", start_time="10:00", end_time="11:00")]
        output = _format_events(events, "Today")
        assert "Meeting" in output
        assert "10:00" in output

    def test_multiple_events(self):
        events = [
            CalendarEvent(summary="Event 1"),
            CalendarEvent(summary="Event 2"),
        ]
        output = _format_events(events, "Today")
        assert "Event 1" in output
        assert "Event 2" in output

    def test_event_with_location(self):
        event = CalendarEvent(summary="Meeting", location="Room A")
        output = _format_events([event], "Today")
        assert "Room A" in output

    def test_event_with_description(self):
        event = CalendarEvent(summary="Meeting", description="Discuss Q2 results")
        output = _format_events([event], "Today")
        assert "Q2" in output


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestCalendarPluginMetadata:
    def test_plugin_name(self):
        plugin = CalendarPlugin()
        assert plugin.name == "calendar"

    def test_plugin_description(self):
        plugin = CalendarPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_is_baseplugin_subclass(self):
        assert issubclass(CalendarPlugin, BasePlugin)


# ============================================================
# Plugin Execution Tests
# ============================================================


class TestCalendarPluginExecute:
    def test_empty_input(self):
        plugin = CalendarPlugin()
        result = plugin.execute("")
        assert result.success is True  # Shows help by default

    def test_help_command(self):
        plugin = CalendarPlugin()
        result = plugin.execute("help")
        assert result.success is True
        assert "Commands" in result.output or "help" in result.output.lower()

    def test_no_api_key(self, monkeypatch):
        """Without API key, commands should return error."""
        monkeypatch.delenv("GOOGLE_CALENDAR_API_KEY", raising=False)
        plugin = CalendarPlugin()
        result = plugin.execute("today")
        assert result.success is False
        assert "API" in result.error or "GOOGLE" in result.error

    def test_today_command(self, monkeypatch):
        """'today' command should fetch today's events."""
        monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", "test_key")
        plugin = CalendarPlugin()

        with patch("src.plugins.calendar_sync._fetch_events", return_value=[]):
            result = plugin.execute("today")
        assert result.success is True

    def test_upcoming_command(self, monkeypatch):
        """'upcoming 3' should fetch 3 days of events."""
        monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", "test_key")
        plugin = CalendarPlugin()

        with patch("src.plugins.calendar_sync._fetch_events", return_value=[]):
            result = plugin.execute("upcoming 3")
        assert result.success is True

    def test_week_command(self, monkeypatch):
        """'week' should fetch 7 days of events."""
        monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", "test_key")
        plugin = CalendarPlugin()

        with patch("src.plugins.calendar_sync._fetch_events", return_value=[]):
            result = plugin.execute("week")
        assert result.success is True

    def test_invalid_command(self, monkeypatch):
        """Invalid command should return error with available commands."""
        monkeypatch.setenv("GOOGLE_CALENDAR_API_KEY", "test_key")
        plugin = CalendarPlugin()

        with patch("src.plugins.calendar_sync._fetch_events", return_value=[]):
            result = plugin.execute("invalid_command_xyz")
        assert result.success is False
