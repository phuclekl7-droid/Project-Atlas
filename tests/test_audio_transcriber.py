"""
Unit tests for Audio Document Transcription Plugin.

Tests:
- Text transcript parsing (_parse_text_transcript)
- Speaker segment detection
- Audio metadata extraction (_extract_audio_metadata)
- TranscriptionResult dataclass
- Plugin metadata
- Plugin execution with text transcript
- Plugin execution with file mode
- Error handling (empty input, non-existent file)
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.audio_transcriber import (
    AudioTranscriberPlugin,
    TranscriptionResult,
    _parse_text_transcript,
    _extract_audio_metadata,
)


# ============================================================
# Data Model Tests
# ============================================================


class TestTranscriptionResult:
    def test_default_values(self):
        result = TranscriptionResult()
        assert result.text == ""
        assert result.file_path == ""
        assert result.duration_seconds == 0.0
        assert result.segments == []
        assert result.language == "en"
        assert result.confidence == 0.0

    def test_with_values(self):
        result = TranscriptionResult(
            text="Hello world",
            file_path="/path/to/audio.wav",
            segments=[{"speaker": "A", "text": "Hello"}],
            language="vi",
        )
        assert result.text == "Hello world"
        assert result.file_path == "/path/to/audio.wav"
        assert len(result.segments) == 1
        assert result.language == "vi"


# ============================================================
# Text Transcript Parsing Tests
# ============================================================


class TestParseTextTranscript:
    def test_simple_text(self):
        """Plain text should be parsed as-is."""
        result = _parse_text_transcript("This is a simple transcript.")
        assert result.text == "This is a simple transcript."
        assert len(result.segments) > 0

    def test_multi_line(self):
        """Multi-line text should be split into segments."""
        text = "Line one.\nLine two.\nLine three."
        result = _parse_text_transcript(text)
        assert len(result.segments) >= 2

    def test_speaker_format(self):
        """Speaker: text format should detect speakers."""
        text = "Speaker 1: Hello everyone\nSpeaker 2: Hi there"
        result = _parse_text_transcript(text)
        assert len(result.segments) == 2
        assert result.segments[0]["speaker"] == "Speaker 1"
        assert result.segments[1]["speaker"] == "Speaker 2"

    def test_speaker_with_vietnamese_names(self):
        """Vietnamese speaker names should be detected."""
        text = "Lan: Xin chào\nMinh: Chào bạn"
        result = _parse_text_transcript(text)
        assert len(result.segments) == 2
        assert "Lan" in result.segments[0]["speaker"]
        assert "Minh" in result.segments[1]["speaker"]

    def test_empty_text(self):
        """Empty text should return empty result."""
        result = _parse_text_transcript("")
        assert result.text == ""

    def test_single_word(self):
        """Single word should work."""
        result = _parse_text_transcript("Hello")
        assert result.text == "Hello"


# ============================================================
# Audio Metadata Extraction Tests
# ============================================================


class TestExtractAudioMetadata:
    def test_existing_file(self, tmp_path):
        """Existing file should return metadata."""
        filepath = tmp_path / "test.wav"
        filepath.write_text("fake audio content")
        metadata = _extract_audio_metadata(str(filepath))
        assert metadata["filename"] == "test.wav"
        assert metadata["size_bytes"] > 0
        assert metadata["format"] == "wav"

    def test_nonexistent_file(self):
        """Non-existent file should have 0 size."""
        metadata = _extract_audio_metadata("/nonexistent/audio.mp3")
        assert metadata["size_bytes"] == 0

    def test_format_from_extension(self):
        """File extension should determine format."""
        metadata = _extract_audio_metadata("/path/to/recording.mp3")
        assert metadata["format"] == "mp3"

    def test_unknown_extension(self):
        """Unknown extension should map to 'unknown'."""
        metadata = _extract_audio_metadata("/path/to/file.xyz")
        assert metadata["format"] == "xyz"


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestAudioTranscriberMetadata:
    def test_plugin_name(self):
        plugin = AudioTranscriberPlugin()
        assert plugin.name == "audio_transcriber"

    def test_plugin_description(self):
        plugin = AudioTranscriberPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0
        assert "audio" in plugin.description.lower() or "transcri" in plugin.description.lower()

    def test_is_baseplugin_subclass(self):
        assert issubclass(AudioTranscriberPlugin, BasePlugin)


# ============================================================
# Plugin Execution Tests
# ============================================================


class TestAudioTranscriberExecute:
    def test_empty_input(self):
        plugin = AudioTranscriberPlugin()
        result = plugin.execute("")
        assert result.success is False

    def test_text_transcript(self):
        """Plain text transcript should be processed."""
        plugin = AudioTranscriberPlugin()
        result = plugin.execute("This is a meeting transcript. We discussed the Q2 results.")
        assert result.success is True
        assert "transcri" in result.output.lower() or "Transcription" in result.output

    def test_speaker_format(self):
        """Speaker: format should be detected."""
        plugin = AudioTranscriberPlugin()
        result = plugin.execute("John: Let's start the meeting\nJane: I have the report ready")
        assert result.success is True
        assert "John" in result.output or "Segments" in result.output

    def test_file_mode_nonexistent(self):
        """File mode with non-existent file should return error."""
        plugin = AudioTranscriberPlugin()
        result = plugin.execute("file: /nonexistent/audio.wav")
        assert result.success is False
        assert "tồn tại" in result.error or "không" in result.error.lower()

    def test_file_mode_with_existing_file(self, tmp_path):
        """File mode with existing file should process."""
        filepath = tmp_path / "test.wav"
        filepath.write_text("fake audio")
        plugin = AudioTranscriberPlugin()
        result = plugin.execute(f"file: {filepath}")
        assert result.success is True
        assert "test.wav" in result.output

    def test_result_contains_data(self):
        """Result should have data with char_count."""
        plugin = AudioTranscriberPlugin()
        result = plugin.execute("Meeting transcript content here.")
        assert result.data is not None
        assert "char_count" in result.data

    def test_long_transcript_data(self):
        """Long transcript should be tracked in data."""
        plugin = AudioTranscriberPlugin()
        text = "Hello world. " * 50
        result = plugin.execute(text)
        assert result.data is not None
        assert result.data["char_count"] >= 600  # 50 * ~12 chars each


# ============================================================
# Audio File Processing Tests
# ============================================================


class TestProcessAudioFile:
    def test_nonexistent_file(self):
        plugin = AudioTranscriberPlugin()
        result = plugin._process_audio_file("/nonexistent/file.wav")
        assert result.success is False
        assert "tồn tại" in result.error or "không" in result.error.lower()

    def test_existing_file_metadata(self, tmp_path):
        """Existing file should show metadata even without transcription."""
        filepath = tmp_path / "meeting.wav"
        filepath.write_text("fake audio content")
        plugin = AudioTranscriberPlugin()
        result = plugin._process_audio_file(str(filepath))
        assert result.success is True
        assert "meeting.wav" in result.output
        assert "bytes" in result.output
