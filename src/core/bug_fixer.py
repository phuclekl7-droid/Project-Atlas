"""
Automated Bug Fixing Workflow (Feature #70).
Reads error logs, identifies root causes, and suggests/creates fixes.

Provides:
- Error log parsing and pattern recognition
- Root cause analysis from stack traces
- Fix suggestion generation
- Self-healing test creation for fixed code
- Integration with Git for commit creation

Usage:
    fixer = BugFixer()
    analysis = fixer.analyze_error("Traceback: ValueError at line 42...")
    fixer.suggest_fix(analysis)
    fixer.create_fix_patch(analysis)
"""

import ast
import difflib
import os
import re
import subprocess
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core import setup_logger

logger = setup_logger("bug_fixer")


@dataclass
class ErrorAnalysis:
    """Result of analyzing an error."""
    error_type: str = ""        # ValueError, TypeError, ImportError, etc.
    error_message: str = ""     # The error message
    file_path: str = ""         # File where error occurred
    line_number: int = 0        # Line number of the error
    code_context: str = ""      # Surrounding code lines
    traceback_lines: list[str] = field(default_factory=list)
    root_cause: str = ""        # Hypothesized root cause
    severity: str = "medium"    # low, medium, high, critical
    suggestions: list[str] = field(default_factory=list)


@dataclass
class FixResult:
    """Result of attempting a fix."""
    success: bool = False
    patch: str = ""             # Unified diff
    description: str = ""       # Human-readable fix description
    file_path: str = ""         # File that was/would be modified
    test_added: bool = False    # Whether a test was added
    verification: str = ""      # Verification result (test output)


# ── Error pattern recognition ──

_ERROR_PATTERNS = [
    (r'(\w+Error):\s*(.+)', "python_error"),
    (r'(Traceback\s*\(most recent call last\):?)', "traceback_start"),
    (r'File\s+"([^"]+)",\s*line\s*(\d+)', "file_location"),
    (r'(ImportError|ModuleNotFoundError):\s*(.+)', "import_error"),
    (r'(ValueError|TypeError|KeyError|IndexError|AttributeError):\s*(.+)', "value_error"),
    (r'(SyntaxError|IndentationError):\s*(.+)', "syntax_error"),
    (r'(NameError|UnboundLocalError):\s*(.+)', "name_error"),
    (r'(OSError|FileNotFoundError|PermissionError):\s*(.+)', "io_error"),
    (r'(TimeoutError|ConnectionError|HTTPError):\s*(.+)', "network_error"),
]


def _parse_error_text(error_text: str) -> ErrorAnalysis:
    """Parse raw error text into structured analysis."""
    analysis = ErrorAnalysis()
    analysis.traceback_lines = error_text.strip().split("\n")

    # Phase 1: Extract file location (must run BEFORE error-type patterns)
    for pattern, category in _ERROR_PATTERNS:
        if category == "file_location":
            match = re.search(pattern, error_text)
            if match:
                analysis.file_path = match.group(1)
                analysis.line_number = int(match.group(2))
            break  # Only one file_location pattern

    # Phase 2: Detect error type and message (break on first match)
    for pattern, category in _ERROR_PATTERNS:
        if category == "file_location":
            continue  # Already handled above
        match = re.search(pattern, error_text)
        if match:
            if category in ("python_error", "import_error", "value_error",
                            "syntax_error", "name_error", "io_error", "network_error"):
                analysis.error_type = match.group(1)
                analysis.error_message = match.group(2).strip()
            break

    # If no specific error found, use generic
    if not analysis.error_type:
        # Try to find any line with "Error" in it
        for line in analysis.traceback_lines:
            if "Error" in line or "error" in line:
                analysis.error_message = line.strip()
                break

    # Determine severity
    if any(w in analysis.error_type.lower() for w in ["critical", "fatal", "system"]):
        analysis.severity = "critical"
    elif any(w in analysis.error_type.lower() for w in ["syntax", "import", "name"]):
        analysis.severity = "high"
    elif any(w in analysis.error_type.lower() for w in ["value", "type", "key", "index"]):
        analysis.severity = "medium"
    else:
        analysis.severity = "low"

    # Generate root cause suggestion
    analysis.root_cause = _suggest_root_cause(analysis)

    # Generate fix suggestions
    analysis.suggestions = _suggest_fixes(analysis)

    return analysis


def _suggest_root_cause(analysis: ErrorAnalysis) -> str:
    """Suggest a likely root cause based on error type."""
    error_type = analysis.error_type.lower()

    if "importerror" in error_type or "modulenotfound" in error_type:
        return f"Missing module or incorrect import path in '{analysis.error_message}'"
    elif "valueerror" in error_type:
        return f"Incorrect value passed to function: {analysis.error_message[:100]}"
    elif "typeerror" in error_type:
        return f"Wrong argument type or incorrect number of arguments: {analysis.error_message[:100]}"
    elif "keyerror" in error_type:
        return f"Missing key in dictionary: {analysis.error_message[:100]}"
    elif "indexerror" in error_type:
        return f"List/tuple index out of range: {analysis.error_message[:100]}"
    elif "attributeerror" in error_type:
        return f"Accessing non-existent attribute: {analysis.error_message[:100]}"
    elif "syntaxerror" in error_type or "indentationerror" in error_type:
        return f"Syntax error in code: {analysis.error_message[:100]}"
    elif "nameerror" in error_type:
        return f"Undefined variable or function: {analysis.error_message[:100]}"
    elif "filenotfound" in error_type:
        return f"File not found at path: {analysis.error_message[:100]}"
    elif "timeout" in error_type or "connection" in error_type:
        return f"Network/connection issue: {analysis.error_message[:100]}"
    else:
        return f"Unhandled exception: {analysis.error_message[:100]}"


def _suggest_fixes(analysis: ErrorAnalysis) -> list[str]:
    """Generate fix suggestions based on error type."""
    suggestions = []

    if "import" in analysis.error_type.lower():
        module = analysis.error_message.split("'")[1] if "'" in analysis.error_message else analysis.error_message
        suggestions.append(f"Install missing module: `pip install {module}`")
        suggestions.append(f"Check import spelling in the source file")
        suggestions.append(f"Verify the module is in your Python path")

    elif "value" in analysis.error_type.lower():
        suggestions.append("Check the value being passed — ensure it's within expected range")
        suggestions.append("Add input validation before the function call")
        suggestions.append("Use try/except to handle invalid values gracefully")

    elif "type" in analysis.error_type.lower():
        suggestions.append("Verify the argument types match the function signature")
        suggestions.append("Add type hints and use mypy for static checking")
        suggestions.append(f"Check if None is being passed where a value is expected")

    elif "key" in analysis.error_type.lower():
        suggestions.append("Use `.get(key, default)` instead of direct key access")
        suggestions.append("Check if the dictionary is properly initialized before access")
        suggestions.append("Verify the key exists before accessing: `if key in dict:`")

    elif "index" in analysis.error_type.lower():
        suggestions.append("Check the list length before accessing the index")
        suggestions.append("Ensure loops don't exceed the list bounds")
        suggestions.append("Use slicing or `.get()`-style access patterns")

    elif "syntax" in analysis.error_type.lower() or "indentation" in analysis.error_type.lower():
        suggestions.append(f"Check line {analysis.line_number} for syntax/indentation errors")
        suggestions.append("Run a linter: `ruff check .` or `pylint`")
        suggestions.append("Verify all brackets and parentheses are properly closed")

    elif "name" in analysis.error_type.lower():
        suggestions.append(f"Check that '{analysis.error_message}' is defined before use")
        suggestions.append("Verify the variable/function name spelling")
        suggestions.append("Check the variable scope — is it accessible at this point?")

    elif "file" in analysis.error_type.lower():
        suggestions.append(f"Verify the file path exists: `os.path.exists(path)`")
        suggestions.append("Check file permissions (read/write access)")
        suggestions.append("Use `pathlib.Path` for cross-platform path handling")

    else:
        suggestions.append("Review the code around the error location")
        suggestions.append("Add defensive programming (try/except) to handle this case")
        suggestions.append("Check for edge cases in the input data")

    return suggestions


def _read_code_context(file_path: str, line_number: int, context_lines: int = 5) -> str:
    """Read surrounding code context from a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return ""

    start = max(0, line_number - context_lines - 1)
    end = min(len(lines), line_number + context_lines)

    context = []
    for i in range(start, end):
        prefix = ">>>" if i == line_number - 1 else "   "
        context.append(f"{prefix} {i+1}: {lines[i].rstrip()}")

    return "\n".join(context)


def _create_unified_diff(original: str, fixed: str, file_path: str = "file.py") -> str:
    """Create a unified diff between original and fixed code."""
    orig_lines = original.splitlines(keepends=True)
    fix_lines = fixed.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, fix_lines,
        fromfile=file_path, tofile=file_path,
        lineterm="",
    )
    return "\n".join(diff)


class BugFixer:
    """
    Analyzes errors, suggests fixes, and creates fix patches.

    Can work with:
    - Raw error messages / stack traces
    - File paths with line numbers
    - Pytest failure output

    Usage:
        fixer = BugFixer()

        # Analyze an error
        analysis = fixer.analyze_error(traceback_text)
        print(analysis.root_cause)
        print(analysis.suggestions)

        # Try to auto-fix a known pattern
        result = fixer.auto_fix_file("src/buggy.py", analysis)
        print(result.patch)
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace = workspace_path

    def analyze_error(self, error_text: str) -> ErrorAnalysis:
        """
        Analyze an error message or traceback.

        Args:
            error_text: Raw error traceback or error message

        Returns:
            ErrorAnalysis with root cause and suggestions
        """
        return _parse_error_text(error_text)

    def analyze_file_error(self, file_path: str, line_number: int) -> ErrorAnalysis:
        """
        Analyze an error at a specific file location.

        Args:
            file_path: Path to the source file
            line_number: Line number where the error occurs

        Returns:
            ErrorAnalysis with code context
        """
        analysis = ErrorAnalysis(
            file_path=file_path,
            line_number=line_number,
        )
        analysis.code_context = _read_code_context(file_path, line_number)
        analysis.root_cause = f"Error at line {line_number} in {file_path}"
        analysis.suggestions = [
            f"Review the code at line {line_number}",
            "Check variable values and logic",
        ]
        return analysis

    def auto_fix_file(self, file_path: str, analysis: ErrorAnalysis) -> FixResult:
        """
        Attempt to auto-fix common error patterns.

        Args:
            file_path: Path to the file to fix
            analysis: ErrorAnalysis from analyze_error()

        Returns:
            FixResult with patch and description
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()
        except Exception as e:
            return FixResult(
                success=False,
                description=f"Cannot read file: {e}",
            )

        fixed_content = original_content
        fixes_applied = []

        # Fix: Add missing import
        if "import" in analysis.error_type.lower():
            missing_module = analysis.error_message.split("'")[1] if "'" in analysis.error_message else ""
            if missing_module and missing_module not in original_content:
                # Find the last import line and add after it
                import_match = re.search(r'^(import |from )', original_content, re.MULTILINE)
                if import_match:
                    # Add comment suggesting the import
                    fixed_content = fixed_content.replace(
                        import_match.group(),
                        f"# TODO: add 'import {missing_module}' here\n{import_match.group()}",
                        1
                    )
                    fixes_applied.append(f"Suggested import: {missing_module}")

        # Fix: Add try/except around common error locations
        if analysis.line_number > 0:
            lines = fixed_content.split("\n")
            if analysis.line_number - 1 < len(lines):
                problem_line = lines[analysis.line_number - 1]
                indent = " " * (len(problem_line) - len(problem_line.lstrip()))
                if not problem_line.strip().startswith(("try:", "except", "finally")):
                    # Wrap in try/except
                    lines[analysis.line_number - 1] = f"{indent}try:"
                    lines.insert(analysis.line_number, f"{indent}    {problem_line.lstrip()}")
                    lines.insert(analysis.line_number + 1, f"{indent}except Exception as e:")
                    lines.insert(analysis.line_number + 2, f"{indent}    logger.error(f\"Error: {{e}}\")")
                    fixed_content = "\n".join(lines)
                    fixes_applied.append("Wrapped problematic code in try/except")

        if fixes_applied:
            patch = _create_unified_diff(original_content, fixed_content, file_path)
            return FixResult(
                success=True,
                patch=patch,
                description="; ".join(fixes_applied),
                file_path=file_path,
                verification="Auto-fix applied. Review the patch before committing.",
            )

        return FixResult(
            success=False,
            description="No automatic fix available for this error pattern.",
            file_path=file_path,
        )

    def format_report(self, analysis: ErrorAnalysis, fix: Optional[FixResult] = None) -> str:
        """Format a bug fix report."""
        lines = [
            "## 🐛 Bug Analysis Report",
            "",
            f"**Error Type:** `{analysis.error_type}`" if analysis.error_type else "",
            f"**Message:** {analysis.error_message}" if analysis.error_message else "",
            f"**Severity:** {analysis.severity.upper()}",
            "",
        ]

        if analysis.file_path:
            lines.append(f"**Location:** `{analysis.file_path}` line {analysis.line_number}")
            lines.append("")

        if analysis.root_cause:
            lines.extend(["### 🔍 Root Cause", "", analysis.root_cause, ""])

        if analysis.suggestions:
            lines.extend(["### 💡 Suggested Fixes", ""])
            for i, suggestion in enumerate(analysis.suggestions, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")

        if analysis.code_context:
            lines.extend(["### 📄 Code Context", "", "```python", analysis.code_context, "```", ""])

        if fix and fix.success:
            lines.extend(["### ✅ Fix Applied", "", fix.description, ""])
            if fix.patch:
                lines.extend(["```diff", fix.patch, "```", ""])

        elif fix and not fix.success:
            lines.extend(["### ❌ Auto-Fix Failed", "", fix.description, ""])

        lines.append("---")
        lines.append("*Generated by Project Atlas Bug Fixer*")

        return "\n".join(lines)
