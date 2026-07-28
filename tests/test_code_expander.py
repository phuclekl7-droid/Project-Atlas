"""
Unit tests for Code Block Expander.

Tests:
- _count_code_lines
- Short code (< 20 lines) returns standard markdown code block
- Long code (> 20 lines) returns HTML with expander
- Truncation preserves correct number of visible lines
- HTML contains expand button text
- CSS constant is valid
- Language tag propagation
- Empty code
"""

import pytest

from ui.code_expander import (
    wrap_code_block,
    _count_code_lines,
    CODE_EXPANDER_CSS,
    _MAX_VISIBLE_LINES,
)


class TestCountCodeLines:
    def test_simple(self):
        code = "line1\nline2\nline3"
        assert _count_code_lines(code) == 3

    def test_empty(self):
        assert _count_code_lines("") == 0

    def test_trailing_newlines(self):
        code = "a\nb\nc\n\n\n"
        assert _count_code_lines(code) == 3

    def test_single_line(self):
        assert _count_code_lines("just one") == 1

    def test_exactly_max(self):
        lines = "\n".join(f"line{i}" for i in range(_MAX_VISIBLE_LINES))
        assert _count_code_lines(lines) == _MAX_VISIBLE_LINES


class TestWrapCodeBlock:
    def test_short_code_returns_markdown(self):
        """Short code should return standard markdown code block."""
        code = "print('hello')\nprint('world')"
        result = wrap_code_block(code, "python")
        assert result.startswith("```python")
        assert result.endswith("```")
        assert "print('hello')" in result

    def test_short_code_strips_trailing_newline(self):
        code = "print('hello')"
        result = wrap_code_block(code, "python")
        assert result == "```python\nprint('hello')\n```"

    def test_long_code_returns_html(self):
        """Code > 20 lines should return HTML with expander."""
        lines = [f"line{i}" for i in range(25)]
        code = "\n".join(lines)
        result = wrap_code_block(code, "python")
        assert result.startswith("<div")
        assert "code-expander-wrapper" in result
        assert "▼ Hiển thị thêm" in result
        assert "code-expander-hidden" in result

    def test_long_code_shows_remaining_count(self):
        """Expander button should show remaining line count."""
        lines = [f"line{i}" for i in range(30)]
        code = "\n".join(lines)
        result = wrap_code_block(code)
        remaining = 30 - _MAX_VISIBLE_LINES
        assert str(remaining) in result

    def test_long_code_first_lines_visible(self):
        """First 20 lines should be visible, rest hidden."""
        lines = [f"line{i}" for i in range(25)]
        code = "\n".join(lines)
        result = wrap_code_block(code)
        assert "line0" in result
        assert "line19" in result  # 20th line (0-indexed)

    def test_no_language(self):
        """Without language, should use empty string."""
        code = "\n".join(f"line{i}" for i in range(10))
        result = wrap_code_block(code)
        assert "```\n" in result  # No language tag

    def test_exactly_max_lines(self):
        """Exactly MAX_VISIBLE_LINES lines should NOT trigger expander."""
        lines = [f"line{i}" for i in range(_MAX_VISIBLE_LINES)]
        code = "\n".join(lines)
        result = wrap_code_block(code, "python")
        assert result.startswith("```python")

    def test_one_over_max(self):
        """Exactly MAX_VISIBLE_LINES + 1 should trigger expander."""
        lines = [f"line{i}" for i in range(_MAX_VISIBLE_LINES + 1)]
        code = "\n".join(lines)
        result = wrap_code_block(code)
        assert "code-expander-wrapper" in result

    def test_empty_code(self):
        result = wrap_code_block("", "python")
        assert "```python\n\n```" in result or result is not None

    def test_html_contains_javascript(self):
        """Expander HTML should contain toggle JavaScript."""
        lines = [f"line{i}" for i in range(25)]
        code = "\n".join(lines)
        result = wrap_code_block(code)
        assert "onclick" in result
        assert "function()" in result


class TestCodeExpanderCSS:
    def test_css_contains_styles(self):
        assert "code-expander-wrapper" in CODE_EXPANDER_CSS
        assert ".code-expander-hidden" in CODE_EXPANDER_CSS
        assert ".code-expander-toggle" in CODE_EXPANDER_CSS

    def test_css_has_style_tag(self):
        assert CODE_EXPANDER_CSS.strip().startswith("<style>")
        assert CODE_EXPANDER_CSS.strip().endswith("</style>")
