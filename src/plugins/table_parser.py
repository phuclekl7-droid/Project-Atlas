"""
Automatic Table Parsing Plugin (Feature 34)

Extracts structured tabular data from user input — including pipe tables,
CSV blocks, and natural language descriptions of data.

When a table is detected, it's parsed into a structured format (list of dicts)
that can be used by other plugins or displayed in the UI.
"""

import csv
import io
import json
import re
from typing import Any, Optional

from src.plugin import BasePlugin, PluginResult

_PIPE_TABLE_PATTERN = re.compile(
    r"^\|(.+)\|\s*$"        # Header row: | A | B |
    r"^\|[-:| ]+\|\s*$"      # Separator: |---|---|
    r"((?:^\|.+\|\s*$)+)",   # Data rows: | 1 | 2 |
    re.MULTILINE,
)

_CSV_PATTERN = re.compile(
    r"```(?:csv|tsv)\s*\n(.*?)```", re.DOTALL
)


def parse_pipe_table(text: str) -> Optional[list[dict[str, str]]]:
    """Parse a pipe table (Markdown-style) into a list of dicts.

    Args:
        text: Text containing a pipe table

    Returns:
        List of dicts (column_name: value), or None if not parseable
    """
    match = _PIPE_TABLE_PATTERN.search(text)
    if not match:
        return None

    lines = text.strip().split("\n")
    header_line = None
    separator_line = None
    data_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if header_line is None:
            header_line = stripped
        elif separator_line is None:
            separator_line = stripped
        else:
            data_lines.append(stripped)

    if not header_line or not data_lines:
        return None

    # Parse headers
    headers = [h.strip() for h in header_line.strip("|").split("|")]

    # Parse data rows
    result = []
    for dl in data_lines:
        cells = [c.strip() for c in dl.strip("|").split("|")]
        # Pad or trim cells to match headers
        while len(cells) < len(headers):
            cells.append("")
        row = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                row[header] = cells[i]
        result.append(row)

    return result


def parse_csv_block(text: str) -> Optional[list[dict[str, str]]]:
    """Parse a CSV/TSV code block into a list of dicts.

    Args:
        text: Text containing a CSV block in ```csv ... ``` markers

    Returns:
        List of dicts, or None if not parseable
    """
    match = _CSV_PATTERN.search(text)
    if not match:
        return None

    csv_text = match.group(1).strip()
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        return list(reader)
    except Exception:
        return None


def detect_table(text: str) -> Optional[list[dict[str, str]]]:
    """Detect and parse any table-like structure in the text.

    Tries multiple formats:
      1. Pipe tables (Markdown)
      2. CSV/TSV code blocks

    Args:
        text: The input text to analyze

    Returns:
        Parsed table as list of dicts, or None
    """
    if not text:
        return None

    # Try pipe tables first
    table = parse_pipe_table(text)
    if table:
        return table

    # Try CSV blocks
    table = parse_csv_block(text)
    if table:
        return table

    return None


def format_table_as_markdown(table: list[dict[str, str]]) -> str:
    """Format a parsed table back into a Markdown pipe table string.

    Args:
        table: List of dicts (must have consistent keys)

    Returns:
        Markdown pipe table as string
    """
    if not table:
        return ""

    headers = list(table[0].keys())
    lines = []

    # Header
    lines.append("| " + " | ".join(headers) + " |")
    # Separator
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    # Data rows
    for row in table:
        lines.append("| " + " | ".join(row.get(h, "") for h in headers) + " |")

    return "\n".join(lines)


class TableParserPlugin(BasePlugin):
    """Plugin that detects and parses tabular data from user messages."""

    @property
    def name(self) -> str:
        return "table_parser"

    @property
    def description(self) -> str:
        return "Tự động phát hiện và phân tích bảng dữ liệu (pipe tables, CSV)"

    def execute(self, user_input: str) -> PluginResult:
        """
        Detect and parse tables in the input.

        Returns the parsed table as structured data if found.
        """
        if not user_input or not user_input.strip():
            return PluginResult(
                success=False,
                output="",
                plugin_name=self.name,
            )

        table = detect_table(user_input)
        if table:
            markdown = format_table_as_markdown(table)
            return PluginResult(
                success=True,
                output=(
                    f"📊 **Bảng dữ liệu được phát hiện:**\n\n"
                    f"{markdown}\n\n"
                    f"*{len(table)} dòng, {len(table[0])} cột*"
                ),
                plugin_name=self.name,
                data={"table": table, "rows": len(table), "columns": list(table[0].keys())},
            )

        return PluginResult(
            success=False,
            output="",
            plugin_name=self.name,
        )
