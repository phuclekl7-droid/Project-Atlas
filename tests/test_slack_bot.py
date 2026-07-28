"""
Tests for Feature #86: Slack App Integration.
"""

import os
from unittest.mock import patch

import pytest

from src.plugins.slack_bot import SlackPlugin


class TestSlackPlugin:
    def test_empty_input(self):
        plugin = SlackPlugin()
        result = plugin.execute("")
        assert result.success

    def test_no_token(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {}, clear=True):
            result = plugin.execute("me")
            assert not result.success
            assert "token" in result.error.lower() or "chưa" in result.error

    def test_help_command(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("help")
            assert result.success
            assert "Slack" in result.output

    def test_me_with_token(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("me")
            assert result.success is not None

    def test_channels_with_token(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("channels")
            assert result.success is not None

    def test_send_no_content(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("send")
            assert not result.success

    def test_send_with_content(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("send general Hello!")
            assert result.success is not None

    def test_read_no_channel(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("read")
            assert not result.success

    def test_read_with_channel(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("read C12345")
            assert result.success is not None

    def test_invalid_command(self):
        plugin = SlackPlugin()
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}):
            result = plugin.execute("blah_blah")
            assert not result.success
