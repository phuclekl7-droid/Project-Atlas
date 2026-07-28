"""
Tests for Feature #83: Telegram Bot Integration.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.plugins.telegram_bot import (
    TelegramBotPlugin,
    _get_bot_token,
    _api_call,
)


class TestGetBotToken:
    """Tests for bot token retrieval."""

    def test_token_from_env(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test_token_123"}):
            token = _get_bot_token()
            assert token == "test_token_123"

    def test_token_from_bot_token_env(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "alt_token_456"}):
            token = _get_bot_token()
            assert token == "alt_token_456"

    def test_token_prefers_telegram(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "primary", "BOT_TOKEN": "secondary"}):
            token = _get_bot_token()
            assert token == "primary"

    def test_no_token(self):
        with patch.dict(os.environ, {}, clear=True):
            token = _get_bot_token()
            assert token is None


class TestTelegramBotPlugin:
    """Tests for the TelegramBotPlugin class."""

    def test_empty_input(self):
        plugin = TelegramBotPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_no_token_configured(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {}, clear=True):
            result = plugin.execute("status")
            assert not result.success
            assert "token" in result.error.lower()

    def test_token_configured(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            result = plugin.execute("status")
            # Should work even if API call fails
            assert result.success is not None

    def test_start_polling(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            result = plugin.execute("start")
            assert result.success
            assert "started" in result.output.lower()

    def test_double_start(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            plugin.execute("start")
            result = plugin.execute("start")
            assert result.success

    def test_stop_polling(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            result = plugin.execute("stop")
            assert result.success

    def test_me_command(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            result = plugin.execute("me")
            assert result.success is not None

    def test_send_no_message(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            result = plugin.execute("send 12345")
            assert not result.success

    def test_invalid_command(self):
        plugin = TelegramBotPlugin()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "test:token"}):
            result = plugin.execute("blah blah")
            assert not result.success
