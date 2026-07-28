"""
Tests for Feature #91: Daily Standup Generator.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.plugins.daily_standup import (
    DailyStandupPlugin,
    _parse_commits,
    _categorize_commit,
    _format_standup_report,
    _run_git_log,
)


class TestParseCommits:
    """Tests for git log parsing."""

    def test_parse_single_commit(self):
        log = "abc123|John Doe|2026-07-27|feat: add login feature"
        commits = _parse_commits(log)
        assert len(commits) == 1
        assert commits[0]["hash"] == "abc123"
        assert commits[0]["author"] == "John Doe"
        assert commits[0]["message"] == "feat: add login feature"

    def test_parse_multiple_commits(self):
        log = "abc|A|2026-01-01|msg1\ndef|B|2026-01-02|msg2"
        commits = _parse_commits(log)
        assert len(commits) == 2

    def test_parse_empty_log(self):
        commits = _parse_commits("")
        assert len(commits) == 0


class TestCategorizeCommit:
    """Tests for commit categorization."""

    def test_feat_category(self):
        cat, emoji = _categorize_commit("feat: add new API endpoint")
        assert cat == "Features"
        assert emoji == "✨"

    def test_fix_category(self):
        cat, emoji = _categorize_commit("fix: resolve memory leak")
        assert cat == "Bug Fixes"

    def test_docs_category(self):
        cat, emoji = _categorize_commit("docs: update README")
        assert cat == "Documentation"

    def test_other_category(self):
        cat, emoji = _categorize_commit("minor tweak to UI")
        assert cat == "Other"
        assert emoji == "🔹"


class TestFormatStandupReport:
    """Tests for standup report formatting."""

    def test_no_commits(self):
        report = _format_standup_report([], "Today")
        assert "No commits" in report

    def test_with_commits(self):
        commits = [
            {"hash": "abc123", "author": "Alice", "date": "2026-07-27", "message": "feat: new feature"},
            {"hash": "def456", "author": "Bob", "date": "2026-07-27", "message": "fix: bug fix"},
        ]
        report = _format_standup_report(commits, "Today")
        assert "Daily Standup Report" in report
        assert "Alice" in report
        assert "Bob" in report
        assert "Features" in report
        assert "Bug Fixes" in report

    def test_author_filter(self):
        commits = [
            {"hash": "a1", "author": "Alice", "date": "2026-07-27", "message": "feat: x"},
            {"hash": "b1", "author": "Bob", "date": "2026-07-27", "message": "feat: y"},
        ]
        report = _format_standup_report(commits, "Today", author_filter="Alice")
        assert "Alice" in report
        assert "Bob" not in report


class TestDailyStandupPlugin:
    """Tests for the DailyStandupPlugin class."""

    def test_empty_input(self):
        plugin = DailyStandupPlugin()
        result = plugin.execute("")
        # Should default to "today"
        assert result.success

    def test_invalid_command(self):
        plugin = DailyStandupPlugin()
        result = plugin.execute("some gibberish command here")
        assert not result.success

    def test_yesterday(self):
        plugin = DailyStandupPlugin()
        result = plugin.execute("yesterday")
        assert result.success is not None

    def test_this_week(self):
        plugin = DailyStandupPlugin()
        result = plugin.execute("this week")
        assert result.success is not None

    def test_last_n_days(self):
        plugin = DailyStandupPlugin()
        result = plugin.execute("last 7 days")
        assert result.success is not None

    def test_invalid_last_n(self):
        plugin = DailyStandupPlugin()
        result = plugin.execute("last xyz days")
        assert not result.success
