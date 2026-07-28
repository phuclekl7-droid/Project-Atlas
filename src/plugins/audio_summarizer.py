"""
Audio Summarizer (Feature #54).
Summarizes audio content from text transcripts.

Since full audio transcription requires heavy ML models (Whisper),
this plugin focuses on the text-based side:
- Accept pasted transcripts or notes from audio recordings
- Accept YouTube transcript data (from youtube-summarizer pattern)
- Generate structured summaries with key points and action items

Usage:
    AudioSummarizerPlugin.execute("Speaker 1: ... Speaker 2: ...")
    AudioSummarizerPlugin.execute("title: Meeting recording\\n[00:00] Intro...")
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("audio_summarizer")


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio with speaker and timing info."""
    speaker: str = "Speaker"
    text: str = ""
    timestamp: str = ""
    duration: str = ""


@dataclass
class AudioSummary:
    """Generated summary of transcribed audio content."""
    title: str = "Audio Recording"
    duration: str = ""
    speakers: list[str] = field(default_factory=list)
    segments: list[TranscriptSegment] = field(default_factory=list)
    key_topics: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    full_transcript: str = ""


# ── Parsing Functions ──

_TIMESTAMP_RE = re.compile(r'\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?')
_SPEAKER_RE = re.compile(r'^(?:\[?([A-Za-z\s]+?)\]?)\s*[:]\s*(.+)$', re.MULTILINE)
_DIALOGUE_RE = re.compile(r'(Speaker\s*\d+|Person\s*\d+|[\w\s]+?)\s*:\s*(.+?)(?=\n\w+\s*:|\Z)', re.DOTALL)

_FILLER_WORDS = {
    "um", "uh", "ah", "er", "like", "you know", "well", "so", "actually",
    "basically", "literally", "honestly", "right", "okay", "i mean",
}


def _parse_transcript(text: str) -> AudioSummary:
    """Parse raw transcript text into structured AudioSummary."""
    summary = AudioSummary()
    summary.full_transcript = text

    # Extract title
    title_match = re.search(r'(?:title|recording|meeting|audio)\s*[=:]\s*(.+?)[\n\r]', text, re.IGNORECASE)
    if title_match:
        summary.title = title_match.group(1).strip()

    # Extract duration
    dur_match = re.search(r'(?:duration|length|time)\s*[=:]\s*(\d+:\d+(?::\d+)?)', text, re.IGNORECASE)
    if dur_match:
        summary.duration = dur_match.group(1).strip()

    # Parse dialogue lines
    seen_speakers = set()
    for match in _DIALOGUE_RE.finditer(text):
        speaker = match.group(1).strip()
        content = match.group(2).strip()
        if speaker and content:
            seen_speakers.add(speaker)
            # Try to extract timestamp from content
            timestamp = ""
            ts_match = _TIMESTAMP_RE.match(content)
            if ts_match:
                timestamp = ts_match.group(1)
                content = _TIMESTAMP_RE.sub('', content, count=1).strip()

            summary.segments.append(TranscriptSegment(
                speaker=speaker,
                text=content,
                timestamp=timestamp,
            ))

    summary.speakers = sorted(seen_speakers)

    # Extract key points and action items from the text
    if not summary.segments:
        # Plain text — treat whole input as monologue
        summary.segments.append(TranscriptSegment(text=text))
        summary.speakers = ["Speaker"]

    # Generate key points from segments
    for seg in summary.segments:
        cleaned = _clean_filler_words(seg.text)
        if len(cleaned) > 30:
            if any(w in cleaned.lower() for w in ["key", "important", "critical", "main", "crucial"]):
                summary.key_points.append(cleaned[:200])
            if any(w in cleaned.lower() for w in ["action", "todo", "need to", "must", "will", "follow"]):
                summary.action_items.append(cleaned[:200])

    # Extract topics from content
    all_text = " ".join(s.text for s in summary.segments)
    topics = _extract_key_topics(all_text)
    summary.key_topics = topics[:5]

    return summary


def _clean_filler_words(text: str) -> str:
    """Remove filler words from text."""
    words = text.split()
    cleaned = [w for w in words if w.lower().strip(".,!?") not in _FILLER_WORDS]
    return " ".join(cleaned)


def _extract_key_topics(text: str, max_topics: int = 5) -> list[str]:
    """Extract key topics from text using simple frequency analysis."""
    # Find capitalized multi-word phrases that appear to be topics
    topic_candidates = re.findall(r'([A-Z][a-z]+(?:\s+[a-z]+){0,3})', text)
    freq: dict[str, int] = {}
    for candidate in topic_candidates:
        candidate_lower = candidate.lower()
        if len(candidate) > 3 and candidate_lower not in ("the", "this", "that", "with", "from"):
            freq[candidate] = freq.get(candidate, 0) + 1

    sorted_topics = sorted(freq.items(), key=lambda x: -x[1])
    return [t for t, _ in sorted_topics[:max_topics]]


def _format_summary(summary: AudioSummary) -> str:
    """Format audio summary as Markdown."""
    lines = [
        f"## 🎙️ Audio Summary",
        "",
        f"**{summary.title}**",
        "",
    ]

    if summary.duration:
        lines.append(f"- **Duration:** {summary.duration}")
    if summary.speakers:
        lines.append(f"- **Speakers:** {', '.join(summary.speakers)}")
    if summary.segments:
        lines.append(f"- **Segments:** {len(summary.segments)}")
    lines.append("")

    # Key Topics
    if summary.key_topics:
        lines.append("### 🔑 Key Topics")
        lines.append("")
        for topic in summary.key_topics:
            lines.append(f"- {topic}")
        lines.append("")

    # Key Points
    if summary.key_points:
        lines.append("### 📌 Key Points")
        lines.append("")
        for point in summary.key_points[:5]:
            lines.append(f"- {point}")
        lines.append("")

    # Action Items
    if summary.action_items:
        lines.append("### ✅ Action Items")
        lines.append("")
        for item in summary.action_items[:5]:
            lines.append(f"- [ ] {item}")
        lines.append("")

    # Transcript Preview
    if summary.segments:
        lines.append("### 📝 Transcript Preview")
        lines.append("")
        for seg in summary.segments[:10]:  # First 10 segments
            ts = f"[{seg.timestamp}] " if seg.timestamp else ""
            lines.append(f"**{seg.speaker}:** {ts}{seg.text[:200]}")
        lines.append("")
        if len(summary.segments) > 10:
            lines.append(f"*... and {len(summary.segments) - 10} more segments*")
            lines.append("")

    lines.append("---")
    lines.append("*Generated by Project Atlas*")
    return "\n".join(lines)


class AudioSummarizerPlugin(BasePlugin):
    """
    Summarizes audio content from transcribed text.

    Input formats:
    - **Speaker format**: `Speaker 1: Hello. Speaker 2: Hi there.`
    - **Dialogue format**: `Alice: How are you? Bob: I'm good!`
    - **Timestamp format**: `[00:00] Intro [01:30] Main topic...`
    - **Plain text**: Paste the full transcript directly

    Auto-extracts:
    - Speaker identification
    - Key topics and points
    - Action items
    - Duration (if timestamped)

    Examples:
        "Alice: Let's discuss the Q2 goals.\\nBob: I think we should focus on AI.\\nAlice: Agreed. Let's set a deadline."

        "title: Team Standup\\nSpeaker 1: Finished the API integration\\nSpeaker 2: Working on the UI\\nSpeaker 1: Let's review on Friday"
    """

    name = "audio_summarizer"
    description = "Tóm tắt nội dung audio từ bản transcript"

    def execute(self, input_str: str) -> PluginResult:
        """Summarize transcribed audio content."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập nội dung transcript.\\n\\n"
                    "Định dạng hỗ trợ:\\n"
                    "- `Speaker 1: Nội dung` — định dạng hội thoại\\n"
                    "- `[00:00] Nội dung` — có timestamp\\n"
                    "- Văn bản thuần — tự động phát hiện\\n\\n"
                    "Ví dụ:\\n"
                    "`Alice: Chúng ta cần bàn về kế hoạch Q2.\\n"
                    "Bob: Tôi nghĩ nên tập trung vào AI.`"
                )
            )

        try:
            summary = _parse_transcript(text)
            output = _format_summary(summary)

            return PluginResult(
                success=True,
                output=output,
                data={
                    "title": summary.title,
                    "speakers": summary.speakers,
                    "segments": len(summary.segments),
                    "key_topics": summary.key_topics,
                },
            )
        except Exception as e:
            logger.error(f"Audio summarization failed: {e}")
            return PluginResult(
                success=False,
                error=f"Không thể tóm tắt audio: {e}"
            )
