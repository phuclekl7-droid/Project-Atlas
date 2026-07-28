"""
Tests for Feature #54: Audio Summarizer.
"""

import pytest

from src.plugins.audio_summarizer import (
    AudioSummarizerPlugin,
    _parse_transcript,
    _format_summary,
    _clean_filler_words,
    _extract_key_topics,
    TranscriptSegment,
    AudioSummary,
)


class TestCleanFillerWords:
    def test_removes_um(self):
        assert "hello world" in _clean_filler_words("um hello world")

    def test_removes_fillers(self):
        cleaned = _clean_filler_words("so basically like we need to")
        assert "basically" not in cleaned

    def test_preserves_content(self):
        cleaned = _clean_filler_words("we need to finish the project")
        assert "finish" in cleaned


class TestExtractKeyTopics:
    def test_extracts_capitalized(self):
        text = "We discussed Machine Learning and Artificial Intelligence"
        topics = _extract_key_topics(text)
        assert len(topics) >= 1

    def test_empty_text(self):
        assert _extract_key_topics("") == []


class TestParseTranscript:
    def test_parse_dialogue(self):
        text = "Alice: Hello there\nBob: Hi Alice\nAlice: How are you?"
        summary = _parse_transcript(text)
        assert len(summary.segments) >= 2
        assert "Alice" in summary.speakers
        assert "Bob" in summary.speakers

    def test_parse_with_title(self):
        text = "title: Team Standup\nAlice: Finished the API"
        summary = _parse_transcript(text)
        assert "Team Standup" in summary.title

    def test_parse_with_duration(self):
        text = "duration: 30:00\nAlice: Meeting started"
        summary = _parse_transcript(text)
        assert summary.duration == "30:00"

    def test_parse_plain_text(self):
        text = "This is just a long monologue about various topics"
        summary = _parse_transcript(text)
        assert len(summary.segments) >= 1

    def test_empty_text(self):
        summary = _parse_transcript("")
        assert summary.title == "Audio Recording"


class TestFormatSummary:
    def test_format_empty(self):
        summary = AudioSummary()
        output = _format_summary(summary)
        assert "Audio Summary" in output

    def test_format_with_data(self):
        summary = AudioSummary(
            title="Team Meeting",
            speakers=["Alice", "Bob"],
            segments=[TranscriptSegment(speaker="Alice", text="Let's discuss Q2 goals")],
            key_topics=["Q2 Goals"],
        )
        output = _format_summary(summary)
        assert "Team Meeting" in output
        assert "Alice" in output
        assert "Q2 Goals" in output


class TestAudioSummarizerPlugin:
    def test_empty_input(self):
        plugin = AudioSummarizerPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_dialogue_input(self):
        plugin = AudioSummarizerPlugin()
        result = plugin.execute("Alice: Hello\nBob: Hi there\nAlice: How are you?")
        assert result.success
        assert "Audio Summary" in result.output or "Summary" in result.output

    def test_plain_text(self):
        plugin = AudioSummarizerPlugin()
        result = plugin.execute("This meeting covered the quarterly review")
        assert result.success

    def test_with_title(self):
        plugin = AudioSummarizerPlugin()
        result = plugin.execute("title: Sprint Retrospective\nAlice: Good sprint everyone")
        assert result.success
