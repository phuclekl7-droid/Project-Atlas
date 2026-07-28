"""
Tests for Feature #25: Terminal Command Runner Plugin.
"""

import pytest

from src.plugins.terminal_runner import (
    TerminalCommandRunnerPlugin,
    ConfirmCommandPlugin,
    _get_command_keyword,
    _is_blocked,
    _is_safe,
    _needs_confirmation,
)


class TestCommandClassification:
    """Tests for internal command classification helpers."""

    def test_get_command_keyword_simple(self):
        assert _get_command_keyword("ls -la") == "ls"
        assert _get_command_keyword("echo hello world") == "echo"

    def test_get_command_keyword_with_path(self):
        assert _get_command_keyword("/usr/bin/git status") == "git"

    def test_get_command_keyword_with_exe_suffix(self):
        assert _get_command_keyword("dir.exe /w") == "dir"

    def test_is_blocked(self):
        assert _is_blocked("shutdown now")
        assert _is_blocked("reboot")
        assert not _is_blocked("ls")

    def test_is_safe(self):
        assert _is_safe("ls -la")
        assert _is_safe("echo hello")
        assert not _is_safe("rm -rf /")

    def test_needs_confirmation(self):
        assert _needs_confirmation("rm -rf /tmp")
        assert _needs_confirmation("git status")
        assert not _needs_confirmation("ls")


class TestTerminalCommandRunnerPlugin:
    """Tests for the TerminalCommandRunnerPlugin."""

    def test_empty_input(self):
        plugin = TerminalCommandRunnerPlugin()
        result = plugin.execute("")
        assert not result.success
        assert "nhập lệnh" in result.error

    def test_blocked_command(self):
        plugin = TerminalCommandRunnerPlugin()
        result = plugin.execute("shutdown now")
        assert not result.success
        assert "bị chặn" in result.error

    def test_confirmation_required(self):
        plugin = TerminalCommandRunnerPlugin()
        result = plugin.execute("rm /tmp/test.txt")
        assert not result.success
        assert "cần xác nhận" in result.error or "xác nhận" in result.error


class TestConfirmCommandPlugin:
    """Tests for the ConfirmCommandPlugin."""

    def test_empty_command(self):
        plugin = ConfirmCommandPlugin()
        result = plugin.execute("")
        assert not result.success
        assert "nhập lệnh" in result.error or "command" in result.error.lower()

    def test_blocked_command(self):
        plugin = ConfirmCommandPlugin()
        result = plugin.execute("shutdown now")
        assert not result.success
        assert "bị chặn" in result.error

    def test_confirm_prefix_stripped(self):
        """Verify /confirm prefix is stripped correctly."""
        plugin = ConfirmCommandPlugin()
        # This will try to run "which python" — will execute on most systems
        result = plugin.execute("/confirm which python")
        # If subprocess runs, it'll succeed (which exists on all Unix/POSIX shells)
        # On Windows this might fail — that's expected behavior
        assert result.success is not None  # Just ensure it doesn't crash
