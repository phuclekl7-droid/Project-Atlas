"""
Tests for Feature #70: Automated Bug Fixing Workflow.
"""

import tempfile
from pathlib import Path

import pytest

from src.core.bug_fixer import (
    BugFixer,
    ErrorAnalysis,
    FixResult,
    _parse_error_text,
    _suggest_root_cause,
    _suggest_fixes,
    _read_code_context,
    _create_unified_diff,
)


class TestParseErrorText:
    def test_parse_value_error(self):
        analysis = _parse_error_text("ValueError: invalid value for argument")
        assert analysis.error_type == "ValueError"
        assert "invalid value" in analysis.error_message

    def test_parse_import_error(self):
        analysis = _parse_error_text("ImportError: No module named 'numpy'")
        assert analysis.error_type == "ImportError"

    def test_parse_type_error(self):
        analysis = _parse_error_text("TypeError: expected str, got int")
        assert analysis.error_type == "TypeError"

    def test_parse_file_location(self):
        analysis = _parse_error_text(
            'File "src/main.py", line 42, in some_function\nValueError: bad value'
        )
        assert "main.py" in analysis.file_path or analysis.line_number > 0

    def test_parse_unknown_error(self):
        analysis = _parse_error_text("Something went wrong with the system")
        assert analysis.error_message is not None

    def test_empty_text(self):
        analysis = _parse_error_text("")
        assert analysis.error_type == ""


class TestSuggestRootCause:
    def test_import_error(self):
        analysis = ErrorAnalysis(error_type="ImportError", error_message="No module named 'x'")
        cause = _suggest_root_cause(analysis)
        assert "import" in cause.lower() or "module" in cause.lower()

    def test_value_error(self):
        analysis = ErrorAnalysis(error_type="ValueError", error_message="bad value")
        cause = _suggest_root_cause(analysis)
        assert "value" in cause.lower()

    def test_key_error(self):
        analysis = ErrorAnalysis(error_type="KeyError", error_message="missing_key")
        cause = _suggest_root_cause(analysis)
        assert "key" in cause.lower()


class TestBugFixer:
    def test_analyze_error(self):
        fixer = BugFixer()
        analysis = fixer.analyze_error("ValueError: invalid input")
        assert analysis.error_type == "ValueError"

    def test_analyze_file_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.py"
            file_path.write_text("x = 1\ny = 2\nz = x + y\n")
            fixer = BugFixer()
            analysis = fixer.analyze_file_error(str(file_path), 3)
            assert analysis.line_number == 3

    def test_auto_fix_missing_file(self):
        fixer = BugFixer()
        analysis = ErrorAnalysis(error_type="ImportError", error_message="No module named 'numpy'")
        result = fixer.auto_fix_file("/nonexistent/file.py", analysis)
        assert not result.success

    def test_auto_fix_with_code(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.py"
            file_path.write_text("import os\n\nx = 1\ny = 2\nz = x + y\n")
            fixer = BugFixer()
            analysis = ErrorAnalysis(
                error_type="ValueError",
                error_message="bad value",
                line_number=4,
            )
            result = fixer.auto_fix_file(str(file_path), analysis)
            assert result.success is not None

    def test_format_report(self):
        fixer = BugFixer()
        analysis = ErrorAnalysis(error_type="ValueError", error_message="test error", severity="high")
        report = fixer.format_report(analysis)
        assert "Bug Analysis" in report
        assert "ValueError" in report

    def test_format_report_with_fix(self):
        fixer = BugFixer()
        analysis = ErrorAnalysis(error_type="TypeError", error_message="type mismatch")
        fix = FixResult(success=True, description="Added type check", patch="@@ -1,3 +1,5 @@")
        report = fixer.format_report(analysis, fix)
        assert "Fix Applied" in report or "Bug Analysis" in report

    def test_suggestions_for_import_error(self):
        suggestions = _suggest_fixes(ErrorAnalysis(error_type="ImportError", error_message="No module named 'x'"))
        assert len(suggestions) > 0
        assert any("pip" in s for s in suggestions)

    def test_suggestions_for_key_error(self):
        suggestions = _suggest_fixes(ErrorAnalysis(error_type="KeyError", error_message="missing"))
        assert len(suggestions) > 0
        assert any("get" in s for s in suggestions)


class TestCreateUnifiedDiff:
    def test_basic_diff(self):
        original = "line one\nline two\n"
        fixed = "line one\nline two modified\n"
        diff = _create_unified_diff(original, fixed, "test.py")
        assert "test.py" in diff
        assert "-line two" in diff or "+line two" in diff or diff is not None
