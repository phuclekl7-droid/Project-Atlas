"""
Tests for Feature #84: Discord Bot Integration.
"""

import os
from unittest.mock import patch

import pytest

from src.plugins.discord_bot import DiscordPlugin


class TestDiscordPlugin:
    def test_empty_input(self):
        plugin = DiscordPlugin()
        result = plugin.execute("")
        assert result.success

    def test_no_token(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {}, clear=True):
            result = plugin.execute("me")
            assert not result.success
            assert "token" in result.error.lower() or "chưa" in result.error

    def test_help_command(self):
        plugin = DiscordPlugin()
        result = plugin.execute("help")
        assert result.success
        assert "Discord" in result.output or "help" in result.output

    def test_invalid_command(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("invalid_cmd_xyz")
            assert not result.success

    def test_me_command_with_token(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("me")
            assert result.success is not None

    def test_channels_command_with_token(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("channels")
            assert result.success is not None

    def test_send_no_content(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("send")
            assert not result.success

    def test_send_with_content(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("send 12345 Hello!")
            assert result.success is not None

    def test_read_no_channel(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("read")
            assert not result.success

    def test_read_with_channel(self):
        plugin = DiscordPlugin()
        with patch.dict(os.environ, {"DISCORD_BOT_TOKEN": "test_token"}):
            result = plugin.execute("read 12345")
            assert result.success is not None
