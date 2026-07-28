"""
Tests for Feature #99: Meeting Minutes Generator.
"""

import pytest

from src.plugins.meeting_minutes import (
    MeetingMinutesPlugin,
    MeetingMinutes,
    _parse_meeting_notes,
    _format_minutes,
    _extract_patterns,
)


class TestExtractPatterns:
    """Tests for pattern extraction."""

    def test_extract_action_items(self):
        text = "John will write unit tests. Sarah must update the docs."
        items = _extract_patterns(text, [
            r'(?:will|must|needs?\s+to)\s+(.+?)(?:[,.]|$)',
        ])
        assert len(items) >= 2
        assert any("write unit tests" in i for i in items)

    def test_extract_decisions(self):
        text = "Agreed to focus on AI features. Decided to improve testing."
        decisions = _extract_patterns(text, [
            r'(?:decided|agreed)\s+(?:that\s+)?(.+?)(?:[,.]|$)',
        ])
        assert len(decisions) >= 2


class TestParseMeetingNotes:
    """Tests for meeting notes parsing."""

    def test_parse_basic(self):
        notes = "We discussed Q2 budget. Agreed to cut costs. John will research options."
        minutes = _parse_meeting_notes(notes)
        assert minutes.title == "We discussed Q2 budget. Agreed to cut costs. John will research options."[:80]
        assert len(minutes.decisions) >= 1
        assert len(minutes.action_items) >= 1

    def test_parse_with_participants(self):
        notes = "participants: Alice, Bob, Charlie\nWe discussed the sprint."
        minutes = _parse_meeting_notes(notes)
        assert "Alice" in minutes.participants
        assert "Bob" in minutes.participants

    def test_parse_with_title(self):
        notes = "title: Sprint Retrospective\nGreat session!"
        minutes = _parse_meeting_notes(notes)
        assert "Sprint Retrospective" in minutes.title

    def test_parse_with_duration(self):
        notes = "duration: 30min\nDiscussed roadmap."
        minutes = _parse_meeting_notes(notes)
        assert "30" in minutes.duration

    def test_parse_empty_text(self):
        minutes = _parse_meeting_notes("")
        assert minutes.title == "Untitled Meeting"

    def test_parse_with_next_steps(self):
        notes = "Discussed plans.\n\nNext steps: Finalize budget by Friday. Update timeline."
        minutes = _parse_meeting_notes(notes)
        assert len(minutes.next_steps) >= 1


class TestFormatMinutes:
    """Tests for meeting minutes formatting."""

    def test_format_empty(self):
        minutes = MeetingMinutes()
        output = _format_minutes(minutes)
        assert "Meeting Minutes" in output

    def test_format_with_content(self):
        minutes = MeetingMinutes(
            title="Sprint Retro",
            participants=["Alice", "Bob"],
            decisions=["Improve testing"],
            action_items=["Alice will write tests", "Bob will fix CI"],
        )
        output = _format_minutes(minutes)
        assert "Sprint Retro" in output
        assert "Alice" in output
        assert "Improve testing" in output
        assert "Alice will write tests" in output


class TestMeetingMinutesPlugin:
    """Tests for the MeetingMinutesPlugin class."""

    def test_empty_input(self):
        plugin = MeetingMinutesPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_basic_notes(self):
        plugin = MeetingMinutesPlugin()
        result = plugin.execute("We discussed the Q2 budget. Agreed to cut costs by 20%. John will lead the effort.")
        assert result.success
        assert "Meeting Minutes" in result.output

    def test_notes_with_participants(self):
        plugin = MeetingMinutesPlugin()
        result = plugin.execute("participants: Alice, Bob, Charlie\ntitle: Sprint Planning\nDecided to focus on features.")
        assert result.success
        assert "Alice" in result.output
        assert "Bob" in result.output

    def test_notes_with_action_items(self):
        plugin = MeetingMinutesPlugin()
        result = plugin.execute("John will write unit tests. Sarah must update documentation.")
        assert result.success
