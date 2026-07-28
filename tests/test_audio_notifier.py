"""
Unit tests for Audio Notifier.

Tests:
- _generate_ding_wav returns valid WAV bytes
- _get_ding_base64 returns base64 string
- get_ding_html returns a script tag with b64
- get_ding_html respects volume and default_enabled params
- is_notification_enabled checks session state
- WAV header format verification
"""

import base64
import struct

import pytest

from ui.audio_notifier import (
    _generate_ding_wav,
    _get_ding_base64,
    get_ding_html,
    is_notification_enabled,
    render_audio_toggle,
)


class TestGenerateDingWav:
    def test_returns_bytes(self):
        """_generate_ding_wav should return bytes."""
        wav = _generate_ding_wav()
        assert isinstance(wav, bytes)
        assert len(wav) > 44  # WAV header is 44 bytes

    def test_valid_wav_header(self):
        """WAV should have correct RIFF header."""
        wav = _generate_ding_wav()
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"
        assert wav[12:16] == b"fmt "

    def test_wav_format_pcm(self):
        """WAV should be PCM format (1 = uncompressed PCM)."""
        wav = _generate_ding_wav()
        fmt = struct.unpack("<H", wav[20:22])[0]
        assert fmt == 1

    def test_wav_channels(self):
        """WAV should be mono (1 channel)."""
        wav = _generate_ding_wav()
        channels = struct.unpack("<H", wav[22:24])[0]
        assert channels == 1

    def test_wav_sample_rate(self):
        """WAV sample rate should be 22050."""
        wav = _generate_ding_wav()
        rate = struct.unpack("<I", wav[24:28])[0]
        assert rate == 22050

    def test_wav_bits_per_sample(self):
        """Should be 16-bit samples."""
        wav = _generate_ding_wav()
        bps = struct.unpack("<H", wav[34:36])[0]
        assert bps == 16

    def test_custom_duration(self):
        """Custom duration should produce a longer WAV."""
        short = _generate_ding_wav(duration_ms=50)
        long = _generate_ding_wav(duration_ms=300)
        assert len(long) > len(short)

    def test_custom_frequency(self):
        """Custom frequency should still produce valid WAV."""
        wav = _generate_ding_wav(frequency=440)
        assert wav[:4] == b"RIFF"


class TestGetDingBase64:
    def test_returns_string(self):
        b64 = _get_ding_base64()
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_valid_base64(self):
        b64 = _get_ding_base64()
        # Should be valid base64
        decoded = base64.b64decode(b64)
        assert decoded[:4] == b"RIFF"

    def test_cached(self):
        """Subsequent calls should return the same value."""
        b64_1 = _get_ding_base64()
        b64_2 = _get_ding_base64()
        assert b64_1 == b64_2


class TestGetDingHtml:
    def test_returns_script_tag(self):
        html = get_ding_html()
        assert "<script>" in html
        assert "</script>" in html
        assert "audio" in html.lower() or "Audio" in html

    def test_contains_base64(self):
        """HTML should contain base64-encoded WAV data."""
        html = get_ding_html()
        assert "base64," in html

    def test_volume_param(self):
        """Volume should appear in the HTML."""
        html = get_ding_html(volume=0.3)
        assert "0.3" in html

    def test_default_enabled_true(self):
        """default_enabled=True should set __soundEnabled=true."""
        html = get_ding_html(default_enabled=True)
        assert "true" in html

    def test_default_enabled_false(self):
        """default_enabled=False should set __soundEnabled=false."""
        html = get_ding_html(default_enabled=False)
        assert "false" in html


class TestIsNotificationEnabled:
    def test_default_false(self):
        """Without session state, should return False."""
        # Simulate no session state
        import streamlit as st
        if "audio_notifier_enabled" in st.session_state:
            del st.session_state["audio_notifier_enabled"]
        assert is_notification_enabled() is False

    def test_when_enabled(self):
        import streamlit as st
        st.session_state["audio_notifier_enabled"] = True
        assert is_notification_enabled() is True

    def test_when_disabled(self):
        import streamlit as st
        st.session_state["audio_notifier_enabled"] = False
        assert is_notification_enabled() is False
