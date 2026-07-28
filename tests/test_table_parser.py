"""
Unit tests for the Automatic Table Parsing plugin (Feature 34).

Tests pipe table parsing, CSV block parsing, and table detection.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.plugins.table_parser import (
    parse_pipe_table,
    parse_csv_block,
    detect_table,
    format_table_as_markdown,
)


class TestParsePipeTable:
    """Tests for parse_pipe_table()."""

    def test_simple_table(self):
        text = (
            "| Name | Age |\n"
            "|------|-----|\n"
            "| Alice | 30 |\n"
            "| Bob | 25 |"
        )
        result = parse_pipe_table(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["Name"] == "Alice"
        assert result[1]["Age"] == "25"

    def test_no_table(self):
        text = "Hello, this is not a table."
        assert parse_pipe_table(text) is None

    def test_empty_string(self):
        assert parse_pipe_table("") is None

    def test_single_row(self):
        text = "| A | B |\n|---|---|\n| 1 | 2 |"
        result = parse_pipe_table(text)
        assert result is not None
        assert len(result) == 1
        assert result[0]["A"] == "1"


class TestParseCSVBlock:
    """Tests for parse_csv_block()."""

    def test_csv_block(self):
        text = "```csv\nname,age\nAlice,30\nBob,25\n```"
        result = parse_csv_block(text)
        assert result is not None
        assert len(result) == 2
        assert result[0]["name"] == "Alice"

    def test_no_csv(self):
        text = "Just some text"
        assert parse_csv_block(text) is None

    def test_malformed_csv(self):
        text = "```csv\nno,header\n```"
        result = parse_csv_block(text)
        assert result is not None


class TestDetectTable:
    """Tests for detect_table()."""

    def test_detect_pipe_table(self):
        text = "| X | Y |\n|---|---|\n| 1 | 2 |"
        result = detect_table(text)
        assert result is not None
        assert result[0]["X"] == "1"

    def test_detect_csv_block(self):
        text = "```csv\na,b\n1,2\n```"
        result = detect_table(text)
        assert result is not None

    def test_no_table(self):
        assert detect_table("Hello world") is None

    def test_empty(self):
        assert detect_table("") is None


class TestFormatTable:
    """Tests for format_table_as_markdown()."""

    def test_format(self):
        table = [{"Name": "Alice", "Age": "30"}]
        result = format_table_as_markdown(table)
        assert "| Name | Age |" in result
        assert "| Alice | 30 |" in result

    def test_empty_table(self):
        assert format_table_as_markdown([]) == ""
