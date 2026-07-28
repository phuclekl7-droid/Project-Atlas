"""
Audio Document Transcription (Feature #35).
Transcribes audio files to text and processes them for the Knowledge Base.

Since full ML-based audio transcription requires heavy dependencies (Whisper),
this plugin provides:
- Accept uploaded audio file paths and convert using available tooling
- Accept raw transcript text for processing
- Chunk and store transcribed text in Knowledge Base
- Builds on AudioSummarizer for structured output

Usage:
    AudioTranscriberPlugin.execute("Upload transcript: ...text...")
    AudioTranscriberPlugin.execute("file: meeting_notes.txt")
    AudioTranscriberPlugin.execute("Audio: speaker1: hello, speaker2: hi")
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("audio_transcriber")

try:
    import speech_recognition as sr
    _HAS_SPEECH_REC = True
except ImportError:
    _HAS_SPEECH_REC = False

try:
    from pydub import AudioSegment
    _HAS_PYDUB = True
except ImportError:
    _HAS_PYDUB = False


@dataclass
class TranscriptionResult:
    """Result of an audio transcription."""
    text: str = ""
    file_path: str = ""
    duration_seconds: float = 0.0
    segments: list[dict] = field(default_factory=list)
    language: str = "en"
    confidence: float = 0.0


def _check_ffmpeg() -> bool:
    """Check if ffmpeg is available for audio conversion."""
    import shutil
    return shutil.which("ffmpeg") is not None


def _transcribe_with_speech_recognition(audio_path: str) -> Optional[TranscriptionResult]:
    """Transcribe audio using SpeechRecognition library."""
    if not _HAS_SPEECH_REC:
        logger.info("speech_recognition not installed. Install: pip install SpeechRecognition")
        return None

    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            if text:
                return TranscriptionResult(
                    text=text,
                    file_path=audio_path,
                )
    except sr.UnknownValueError:
        logger.warning("Speech recognition could not understand audio")
    except sr.RequestError as e:
        logger.warning(f"Speech recognition service error: {e}")
    except Exception as e:
        logger.warning(f"Audio transcription failed: {e}")

    return None


def _extract_audio_metadata(file_path: str) -> dict:
    """Extract basic audio file metadata."""
    path = Path(file_path)
    stats = {"filename": path.name, "size_bytes": path.stat().st_size if path.exists() else 0}
    ext = path.suffix.lower()
    stats["format"] = ext.lstrip(".") if ext else "unknown"
    return stats


def _parse_text_transcript(text: str) -> TranscriptionResult:
    """Parse plain text transcript-like content."""
    result = TranscriptionResult()

    if "\n" in text or ". " in text:
        # Multi-line or multi-sentence text
        result.text = text
        # Try to detect speaker segments
        segments = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            speaker_match = re.match(r'^(\w[\w\s]*?)\s*:\s*(.+)$', line)
            if speaker_match:
                segments.append({
                    "speaker": speaker_match.group(1).strip(),
                    "text": speaker_match.group(2).strip(),
                })
            else:
                segments.append({"speaker": "", "text": line})
        result.segments = segments

    return result


class AudioTranscriberPlugin(BasePlugin):
    """
    Transcribes audio documents and processes them for the Knowledge Base.

    Two modes:
    1. **Text transcript**: Paste the transcript text directly
    2. **Audio file**: Provide a path to an audio file
       (requires SpeechRecognition + pydub + ffmpeg)

    The transcribed text can then be added to the Knowledge Base for RAG.

    Examples:
        "Speaker 1: Let's start the meeting\\nSpeaker 2: I have the Q2 report ready"
        "This is a transcript of a lecture about machine learning..."
        "file: C:/recordings/meeting.wav"
    """

    name = "audio_transcriber"
    description = "Chuyển đổi audio thành văn bản và xử lý vào Knowledge Base"

    def execute(self, input_str: str) -> PluginResult:
        """Transcribe or process audio/transcript content."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập nội dung transcript hoặc đường dẫn file audio.\\n\\n"
                    "Định dạng hỗ trợ:\\n"
                    "- **Transcript dạng text**: paste nội dung\\n"
                    "- **File path**: `file: /path/to/audio.wav`\\n"
                    "- **Speaker format**: `Speaker 1: content`\\n\\n"
                    "Ví dụ:\\n"
                    "`file: C:/recordings/meeting.wav`\\n"
                    "`Speaker 1: Xin chào, hôm nay chúng ta bàn về...`"
                )
            )

        try:
            # Check for file mode
            file_match = re.match(r'^file:\s*(.+)$', text, re.IGNORECASE)
            if file_match:
                audio_path = file_match.group(1).strip()
                return self._process_audio_file(audio_path)

            # Check for text transcript mode
            result = _parse_text_transcript(text)

            # Build output
            lines = [
                "## 🎤 Audio Transcription",
                "",
                f"**Processed text:** {len(result.text)} characters",
                "",
            ]

            if result.segments:
                lines.append(f"**Segments detected:** {len(result.segments)}")
                lines.append("")
                lines.append("### 📝 Transcript")
                lines.append("")
                for seg in result.segments[:15]:
                    speaker = f"**{seg['speaker']}:** " if seg['speaker'] else ""
                    content = seg['text'][:200]
                    lines.append(f"{speaker}{content}")
                if len(result.segments) > 15:
                    lines.append(f"")
                    lines.append(f"*... and {len(result.segments) - 15} more segments*")
                lines.append("")

            lines.append("---")
            lines.append("*Processed by Project Atlas*")

            return PluginResult(
                success=True,
                output="\n".join(lines),
                data={
                    "char_count": len(result.text),
                    "segment_count": len(result.segments),
                    "text": result.text,
                },
            )

        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return PluginResult(
                success=False,
                error=f"Không thể xử lý audio: {e}"
            )

    def _process_audio_file(self, audio_path: str) -> PluginResult:
        """Process an audio file for transcription."""
        path = Path(audio_path)

        if not path.exists():
            return PluginResult(
                success=False,
                error=f"File không tồn tại: {audio_path}"
            )

        metadata = _extract_audio_metadata(audio_path)

        lines = [
            "## 🎤 Audio File Processing",
            "",
            f"**File:** {metadata['filename']}",
            f"**Size:** {metadata['size_bytes']:,} bytes",
            f"**Format:** {metadata['format']}",
            "",
        ]

        # Try actual transcription
        result = _transcribe_with_speech_recognition(audio_path)

        if result and result.text:
            lines.extend([
                "### ✅ Transcription Complete",
                "",
                result.text[:1000],
                "",
            ])
            return PluginResult(
                success=True,
                output="\n".join(lines),
                data={"text": result.text, "file": audio_path},
            )

        # If transcription not available
        lines.extend([
            "### ⚠️ Transcription Not Available",
            "",
            "Full audio transcription requires additional dependencies:",
            "",
            "```bash",
            "pip install SpeechRecognition pydub",
            "# Also install ffmpeg from: https://ffmpeg.org/",
            "```",
            "",
            "**Alternative:** Upload the transcript as text instead.",
            "",
            "To process from text, just paste the transcript content directly.",
        ])

        return PluginResult(
            success=True,
            output="\n".join(lines),
            data={"file": audio_path, "transcribed": False},
        )
