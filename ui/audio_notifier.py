"""
Audio Notifier (Feature: Completion Sound Chime)

Plays a short "ding" sound when the AI finishes generating a response.
Uses a base64-encoded WAV embedded in HTML5 Audio.

Provides:
- get_ding_html() — returns HTML/JS snippet that plays the chime
- render_audio_toggle() — renders a toggle button in the sidebar
- is_notification_enabled() — check if sound is active

The ding sound is a short 440Hz sine-wave beep generated as base64 WAV.
"""

import base64
import struct
import io
import wave
import streamlit as st


# ── Generate a minimal "ding" WAV in memory ──

def _generate_ding_wav(duration_ms: int = 150, frequency: int = 880) -> bytes:
    """
    Generate a short sine-wave "ding" as a WAV file in memory.

    Args:
        duration_ms: Duration in milliseconds (default 150)
        frequency: Pitch in Hz (default 880 = A5, a pleasant 'ding')

    Returns:
        WAV file bytes
    """
    import math
    sample_rate = 22050  # Low sample rate keeps the file tiny
    num_samples = int(sample_rate * duration_ms / 1000)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)          # Mono
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(sample_rate)

        for i in range(num_samples):
            t = i / sample_rate
            # Sine wave with exponential decay envelope
            envelope = 1.0 - (t / (duration_ms / 1000))
            if envelope < 0:
                envelope = 0.0
            sample = int(16000 * envelope * (2 ** 0.5) *
                         math.sin(2 * math.pi * frequency * t))
            wf.writeframes(struct.pack("<h", sample))

    return buf.getvalue()


# Pre-generated base64 ding (cached at module load)
_DING_B64: str = ""


def _get_ding_base64() -> str:
    """Get the base64-encoded ding WAV, cached."""
    global _DING_B64
    if not _DING_B64:
        wav_bytes = _generate_ding_wav()
        _DING_B64 = base64.b64encode(wav_bytes).decode("ascii")
    return _DING_B64


# ── HTML/JS snippet ──

_DING_HTML_TEMPLATE = """\
<script>
(function() {{
    'use strict';
    if (window.__audioNotifierInjected) return;
    window.__audioNotifierInjected = true;

    // Create audio element with embedded base64 ding
    var audio = new Audio("data:audio/wav;base64,{b64}");
    audio.volume = {volume};

    // Expose a global function so Streamlit can call it after response
    window.__playCompletionSound = function() {{
        if (!window.__soundEnabled) return;
        try {{
            audio.currentTime = 0;
            audio.play().catch(function(e) {{}});
        }} catch(e) {{}}
    }};

    // Enable sound by default (user can toggle via sidebar)
    window.__soundEnabled = {default_enabled};
}})();
</script>
"""


def get_ding_html(volume: float = 0.5, default_enabled: bool = False) -> str:
    """
    Get the HTML/JS snippet to inject the completion chime.

    Args:
        volume: Audio volume (0.0–1.0, default 0.5)
        default_enabled: Whether notifications start enabled

    Returns:
        HTML <script> tag string to inject via st.markdown
    """
    b64 = _get_ding_base64()
    return _DING_HTML_TEMPLATE.format(
        b64=b64,
        volume=max(0.0, min(1.0, volume)),
        default_enabled="true" if default_enabled else "false",
    )


def render_audio_toggle() -> None:
    """
    Render a toggle button in the sidebar for enabling/disabling
    the completion notification sound.

    Also exposes JS bridge via st.components.v1.html or session_state.
    Uses st.toggle for the UI, stores preference in session_state.
    """
    key = "audio_notifier_enabled"
    if key not in st.session_state:
        st.session_state[key] = False

    enabled = st.toggle(
        "🔔 Âm thanh thông báo",
        value=st.session_state[key],
        key=key,
        help="Phát tiếng 'ding' khi AI trả lời xong",
    )
    st.session_state[key] = enabled

    # Inject a tiny JS snippet that syncs the window flag
    if enabled:
        st.markdown(
            "<script>if(window.__soundEnabled!==undefined)window.__soundEnabled=true;</script>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<script>if(window.__soundEnabled!==undefined)window.__soundEnabled=false;</script>",
            unsafe_allow_html=True,
        )


def is_notification_enabled() -> bool:
    """Check if the sound notification is enabled in session state."""
    return st.session_state.get("audio_notifier_enabled", False)
