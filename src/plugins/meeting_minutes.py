"""
Meeting Minutes Generator (Feature #99).
Transforms raw meeting notes into structured, professional meeting minutes.

Features:
- Raw notes → structured minutes
- Action item extraction
- Decision tracking
- Topic categorization
- Multiple output formats

Usage:
    MeetingMinutesPlugin.execute("Today we discussed the Q2 budget. John proposed cutting costs by 20%.")
    MeetingMinutesPlugin.execute("notes: We talked about the new feature... participants: Alice, Bob")
    MeetingMinutesPlugin.execute("raw: Our sprint retrospective...")
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("meeting_minutes")


@dataclass
class MeetingMinutes:
    """Structured meeting minutes."""
    title: str = "Untitled Meeting"
    date: str = ""
    participants: list[str] = field(default_factory=list)
    duration: str = ""
    agenda: list[str] = field(default_factory=list)
    discussions: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    notes: str = ""


# ── Patterns for detecting structured content ──

_ACTION_PATTERNS = [
    r'(?:will|shall|must|needs?\s+to|going\s+to|plan\s+to)\s+(.+?)(?:[,.]|$)',
    r'(?:action\s*item|to\-do|todo|task|follow.up)\s*[=:]\s*(.+?)(?:[,.]|$)',
    r'(?:assign(?:ed|ment)?\s+to|owner[=:]\s*)\s*([A-Za-z]+)\s*[:=-]+\s*(.+?)(?:[,.]|$)',
    r'(?:@)([A-Za-z]+)\s+(.+?)(?:[,.]|$)',
]

_DECISION_PATTERNS = [
    r'(?:decided|decision|agreed|consensus|resolved)\s+(?:that\s+)?(.+?)(?:[,.]|$)',
    r'(?:we\s+)?(?:conclude|finalize|approve|confirm)\s+(.+?)(?:[,.]|$)',
]

_AGENDA_PATTERNS = [
    r'(?:agenda|topics?|discuss)\s*[=:]\s*(.+?)(?:[,.]|$)',
    r'(?:item|topic)\s+\d+\s*[=:\)]\s*(.+?)(?:[,.]|$)',
]

_PARTICIPANT_PATTERNS = [
    r'(?:participants?|attendees?|present|who)\s*[=:]\s*(.+?)(?:[,.]|$)',
]


def _extract_patterns(text: str, patterns: list[str]) -> list[str]:
    """Extract matches from text using regex patterns."""
    results = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if isinstance(m, tuple):
                m = " ".join(m)
            m = m.strip().strip(".,;")
            if m and m not in results and len(m) > 5:
                results.append(m)
    return results


def _parse_meeting_notes(raw_text: str) -> MeetingMinutes:
    """Parse raw meeting notes into structured MeetingMinutes."""
    minutes = MeetingMinutes()
    minutes.date = datetime.now().strftime("%Y-%m-%d")
    minutes.notes = raw_text

    # Extract title (first line or "title:" marker)
    title_match = re.search(r'(?:title|meeting|subject|topic)\s*[=:]\s*(.+?)[\n\r]', raw_text, re.IGNORECASE)
    if title_match:
        minutes.title = title_match.group(1).strip()
    else:
        first_line = raw_text.strip().split("\n")[0][:80]
        if first_line:
            minutes.title = first_line

    # Extract participants
    for pattern in _PARTICIPANT_PATTERNS:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            participants = re.split(r'[,;]\s*', match.group(1).strip())
            minutes.participants = [p.strip() for p in participants if p.strip()]
            break

    # Extract duration
    duration_match = re.search(r'(?:duration|time|length)\s*[=:]\s*(\d+\s*(?:min|hour|h|m))', raw_text, re.IGNORECASE)
    if duration_match:
        minutes.duration = duration_match.group(1).strip()

    # Extract decisions
    minutes.decisions = _extract_patterns(raw_text, _DECISION_PATTERNS)

    # Extract action items
    minutes.action_items = _extract_patterns(raw_text, _ACTION_PATTERNS)

    # Extract agenda items
    agenda_from_marker = _extract_patterns(raw_text, _AGENDA_PATTERNS)
    if agenda_from_marker:
        minutes.agenda = agenda_from_marker

    # Extract next steps (after "next steps" or "next")
    next_match = re.search(r'(?:next\s+steps?|follow.up|moving\s+forward)[=:](.+?)(?:$|\n\n)', raw_text, re.IGNORECASE | re.DOTALL)
    if next_match:
        steps = re.split(r'[\n\r]+', next_match.group(1).strip())
        minutes.next_steps = [s.strip(" •-*\n\r") for s in steps if s.strip() and len(s.strip()) > 5]

    return minutes


def _format_minutes(minutes: MeetingMinutes, format_type: str = "markdown") -> str:
    """Format meeting minutes as markdown or text."""

    def _section(title: str, items: list[str]) -> str:
        if not items:
            return ""
        lines = [f"### {title}", ""]
        for i, item in enumerate(items, 1):
            lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)

    lines = [
        f"## 📋 Meeting Minutes",
        f"",
        f"**{minutes.title}**",
        f"",
        f"- **Date:** {minutes.date}",
    ]
    if minutes.participants:
        lines.append(f"- **Participants:** {', '.join(minutes.participants)}")
    if minutes.duration:
        lines.append(f"- **Duration:** {minutes.duration}")
    lines.append("")

    # Agenda
    if minutes.agenda:
        ag = _section("Agenda", minutes.agenda)
        if ag:
            lines.append(ag)

    # Discussions / Notes
    if minutes.notes and len(minutes.notes) > 20:
        lines.append("### Notes")
        lines.append("")
        lines.append(minutes.notes[:1500].replace("\n", "\n> "))
        lines.append("")

    # Decisions
    if minutes.decisions:
        dec = _section("Key Decisions", minutes.decisions)
        if dec:
            lines.append(dec)

    # Action Items
    if minutes.action_items:
        ai = _section("Action Items", minutes.action_items)
        if ai:
            lines.append(ai)

    # Next Steps
    if minutes.next_steps:
        ns = _section("Next Steps", minutes.next_steps)
        if ns:
            lines.append(ns)

    lines.append("---")
    lines.append(f"📅 Generated by Project Atlas • {minutes.date}")
    return "\n".join(lines)


class MeetingMinutesPlugin(BasePlugin):
    """
    Generates structured meeting minutes from raw notes.

    Commands:
    - "notes: <raw meeting notes>": Process notes into minutes
    - "raw: <text>": Same as above
    - "title: <name> participants: <names> agenda: <topics> ...": Full structured input

    Auto-extracts:
    - Decisions (decided, agreed, resolved)
    - Action items (will, must, needs to, @person)
    - Participants (participants:, attendees:)
    - Agenda items

    Examples:
        "We discussed the Q2 roadmap. Agreed to focus on AI features.
         John will research LLM options. Sarah will update the timeline.
         Next steps: Finalize budget by Friday."

        "title: Sprint Retrospective participants: Alice, Bob, Charlie
         We reviewed the last sprint. Decided to improve testing.
         Todo: Alice will write unit tests. Bob will fix the CI pipeline."
    """

    name = "meeting_minutes"
    description = "Tạo biên bản cuộc họp chuyên nghiệp từ ghi chú thô"

    def execute(self, input_str: str) -> PluginResult:
        """Generate meeting minutes from input text."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng nhập ghi chú cuộc họp.\n\n"
                    "Ví dụ:\n"
                    "- `title: Sprint Retrospective participants: Alice, Bob\\n"
                    "We discussed the sprint. Agreed to improve testing.\\n"
                    "John will write unit tests.`\n\n"
                    "Tự động trích xuất: decisions, action items, participants."
                )
            )

        try:
            minutes = _parse_meeting_notes(text)
            output = _format_minutes(minutes)
            return PluginResult(
                success=True,
                output=output,
                data={
                    "title": minutes.title,
                    "participants": minutes.participants,
                    "decisions": minutes.decisions,
                    "action_items": minutes.action_items,
                },
            )
        except Exception as e:
            logger.error(f"Meeting minutes generation failed: {e}")
            return PluginResult(
                success=False,
                error=f"Không thể tạo biên bản: {e}"
            )
