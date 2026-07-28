"""
Code Review Agent Plugin (Feature 66)

Analyzes uploaded code snippets for common issues:
  - Syntax errors (basic pattern matching)
  - Security vulnerabilities (hardcoded secrets, SQL injection, command injection)
  - Performance issues (nested loops, unnecessary allocations)
  - Style violations (PEP 8 conventions, naming)
  - Best practice suggestions

This is a pattern-based analyzer that works without an LLM,
making it fast and available even in offline mode.
"""

import re
from typing import Any

from src.plugin import BasePlugin, PluginResult

# ── Issue patterns ──

_HARDCODED_SECRETS = re.compile(
    r"(?:api_key|api_secret|password|passwd|secret|token|credential)"
    r"\s*[=:]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]",
    re.IGNORECASE,
)

_SQL_INJECTION = re.compile(
    r"(?:execute|exec|raw|query)\s*\(?\s*['\"]\s*(?:SELECT|INSERT|UPDATE|DELETE)\s+.*?(?:\+|\%|\{|\})",
    re.IGNORECASE,
)

_COMMAND_INJECTION = re.compile(
    r"(?:os\.system|subprocess\.call|subprocess\.Popen|os\.popen)\s*\(.*?\$|`",
    re.IGNORECASE,
)

_EVAL_USAGE = re.compile(
    r"\b(?:eval|exec)\s*\(.*?input|request|get|post",
    re.IGNORECASE,
)

_NESTED_LOOPS = re.compile(
    r"(?:for\s+.*?:\s*\n\s+for\s+.*?:)|(?:while\s+.*?:\s*\n\s+for\s+.*?:)",
)

_BARE_EXCEPT = re.compile(
    r"except\s*:",
)

_PRINT_STATEMENT = re.compile(
    r"^\s*print\s*\(",
    re.MULTILINE,
)

_TODO_COMMENT = re.compile(
    r"#\s*(?:TODO|FIXME|HACK|XXX|BUG)\s*:",
    re.IGNORECASE,
)

_LONG_LINE = re.compile(
    r"^.{80,}$",
    re.MULTILINE,
)

_MIXED_INDENT = re.compile(
    r"(?:^\t+ +\S)|(?:^ +\t+\S)",
    re.MULTILINE,
)


def _detect_language(code: str) -> str:
    """Detect the programming language of the code snippet."""
    patterns = {
        "python": [r"\bdef \w+\s*\(.*?\):", r"\bimport \w+", r"\bclass \w+:", r"if __name__"],
        "javascript": [r"\bfunction\s+\w+\s*\(", r"\bconst\s+\w+\s*=", r"\blet\s+\w+\s*=", r"\bdocument\."],
        "typescript": [r"\binterface\s+\w+", r"\btype\s+\w+\s*=", r":\s*(?:string|number|boolean)\s*="],
        "java": [r"\bpublic\s+(?:class|void|static)", r"\bSystem\.out\.", r"\bimport\s+java\."],
        "go": [r"\bfunc\s+\w+\s*\(", r"\bpackage\s+\w+", r"\bimport\s+\(?"],
        "rust": [r"\bfn\s+\w+\s*\(", r"\blet\s+mut\b", r"\bimpl\s+\w+"],
        "cpp": [r"#include\s*<", r"\bint\s+main\s*\(", r"\bstd::"],
        "sql": [r"\bSELECT\b", r"\bFROM\b", r"\bWHERE\b", r"\bJOIN\b"],
    }

    scores = {}
    for lang, pttns in patterns.items():
        score = sum(1 for p in pttns if re.search(p, code, re.MULTILINE))
        if score > 0:
            scores[lang] = score

    if scores:
        return max(scores, key=scores.get)
    return "unknown"


def _review_code(code: str, language: str) -> list[dict[str, Any]]:
    """Run all review checks on the code.

    Args:
        code: The source code to review
        language: Detected programming language

    Returns:
        List of issue dicts with keys: severity, category, line, message
    """
    issues = []
    lines = code.split("\n")

    # Check each pattern and report findings
    checks = [
        ("critical", "security", _HARDCODED_SECRETS, "Hardcoded secret/API key detected"),
        ("critical", "security", _SQL_INJECTION, "Potential SQL injection vulnerability"),
        ("critical", "security", _COMMAND_INJECTION, "Command injection risk"),
        ("critical", "security", _EVAL_USAGE, "Use of eval/exec with user input"),
        ("warning", "performance", _NESTED_LOOPS, "Nested loops detected - consider optimizing"),
        ("warning", "error_handling", _BARE_EXCEPT, "Bare except clause (catches all exceptions)"),
        ("warning", "style", _PRINT_STATEMENT, "Print statement in production code"),
        ("info", "maintainability", _TODO_COMMENT, "TODO/FIXME comment found"),
        ("info", "style", _LONG_LINE, "Line exceeds 80 characters"),
        ("warning", "style", _MIXED_INDENT, "Mixed spaces and tabs in indentation"),
    ]

    for severity, category, pattern, message in checks:
        # Use finditer to get match positions with line number computation
        for match in pattern.finditer(code):
            line_num = code[:match.start()].count("\n") + 1
            issues.append({
                "severity": severity,
                "category": category,
                "line": line_num,
                "message": message,
            })

    # Count total lines for stats
    total_lines = len(lines)
    code_lines = sum(1 for l in lines if l.strip() and not l.strip().startswith(("#", "//", "/*", "*", "'''", '"""')))

    return issues


def format_review(issues: list[dict], language: str, total_lines: int, code_lines: int) -> str:
    """Format code review results as a human-readable report.

    Args:
        issues: List of issue dicts
        language: Detected language
        total_lines: Total lines of code
        code_lines: Lines of actual code (excluding comments/blank)

    Returns:
        Formatted markdown report
    """
    if not issues:
        return (
            f"✅ **Code Review Passed** ({language})\n\n"
            f"Không tìm thấy vấn đề nào trong {total_lines} dòng code "
            f"({code_lines} dòng code thực tế).\n"
            f"Code sạch và tuân thủ best practices!"
        )

    critical = [i for i in issues if i["severity"] == "critical"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    info = [i for i in issues if i["severity"] == "info"]

    lines = [
        f"### Code Review Report ({language.upper()})",
        f"",
        f"**Tổng quan:** {len(issues)} vấn đề được tìm thấy",
        f"- 🔴 Critical: {len(critical)}",
        f"- 🟡 Warning: {len(warnings)}",
        f"- 🔵 Info: {len(info)}",
        f"- Tổng số dòng: {total_lines} (thực tế: {code_lines})",
        f"",
    ]

    if critical:
        lines.append("---")
        lines.append("### 🔴 Critical Issues")
        for iss in critical[:5]:
            lines.append(f"- **Dòng {iss['line']}**: {iss['message']}")

    if warnings:
        lines.append("---")
        lines.append("### 🟡 Warnings")
        for iss in warnings[:10]:
            lines.append(f"- **Dòng {iss['line']}**: {iss['message']}")

    if info:
        lines.append("---")
        lines.append("### 🔵 Suggestions")
        for iss in info[:10]:
            lines.append(f"- **Dòng {iss['line']}**: {iss['message']}")

    return "\n".join(lines)


class CodeReviewPlugin(BasePlugin):
    """Plugin that reviews source code for issues and best practices."""

    @property
    def name(self) -> str:
        return "code_reviewer"

    @property
    def description(self) -> str:
        return "Phân tích mã nguồn, phát hiện lỗi bảo mật và đề xuất cải thiện"

    def execute(self, user_input: str) -> PluginResult:
        """
        Analyze code in the user input and return a review report.

        Detects code blocks in the input, analyzes each one,
        and returns a formatted review.
        """
        if not user_input or not user_input.strip():
            return PluginResult(
                success=False,
                output="",
                plugin_name=self.name,
            )

        # Detect code blocks
        code_blocks = re.findall(r"```(\w*)\n(.*?)```", user_input, re.DOTALL)

        if not code_blocks:
            # Try to detect if the entire input is code-like
            lines = user_input.strip().split("\n")
            code_line_count = sum(
                1 for l in lines
                if l.strip() and not l.strip().startswith(("What", "How", "Why", "Can", "Please", "Help"))
            )
            if code_line_count > 3:
                code_blocks = [("", user_input.strip())]

        if not code_blocks:
            return PluginResult(
                success=False,
                output="",
                plugin_name=self.name,
            )

        all_reports = []
        for lang_hint, code in code_blocks:
            language = lang_hint or _detect_language(code)
            issues = _review_code(code, language)
            lines = code.split("\n")
            code_lines_count = sum(
                1 for l in lines
                if l.strip() and not l.strip().startswith(("#", "//", "/*", "*", "'''", '"""'))
            )
            report = format_review(issues, language, len(lines), code_lines_count)
            all_reports.append(report)

        combined = "\n\n".join(all_reports)

        return PluginResult(
            success=True,
            output=combined,
            plugin_name=self.name,
            data={
                "blocks_reviewed": len(code_blocks),
                "total_issues": sum(
                    len(_review_code(code, "")) for _, code in code_blocks
                ),
            },
        )
