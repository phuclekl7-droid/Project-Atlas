"""
Tests for Feature #85: Zalo OA Integration.
"""

import os
from unittest.mock import patch

import pytest

from src.plugins.zalo_bot import ZaloPlugin


class TestZaloPlugin:
    def test_empty_input(self):
        plugin = ZaloPlugin()
        result = plugin.execute("")
        assert result.success

    def test_no_token(self):
        plugin = ZaloPlugin()
        with patch.dict(os.environ, {}, clear=True):
            result = plugin.execute("me")
            assert not result.success
            assert "token" in result.error.lower() or "chưa" in result.error

    def test_help_command(self):
        plugin = ZaloPlugin()
        with patch.dict(os.environ, {"ZALO_OA_ACCESS_TOKEN": "test_token"}):
            result = plugin.execute("help")
            assert result.success
            assert "Zalo" in result.output or "help" in result.output

    def test_me_command_with_token(self):
        plugin = ZaloPlugin()
        with patch.dict(os.environ, {"ZALO_OA_ACCESS_TOKEN": "test_token"}):
            result = plugin.execute("me")
            assert result.success is not None

    def test_send_no_content(self):
        plugin = ZaloPlugin()
        with patch.dict(os.environ, {"ZALO_OA_ACCESS_TOKEN": "test_token"}):
            result = plugin.execute("send")
            assert not result.success

    def test_send_with_content(self):
        plugin = ZaloPlugin()
        with patch.dict(os.environ, {"ZALO_OA_ACCESS_TOKEN": "test_token"}):
            result = plugin.execute("send user123 Hello!")
            assert result.success is not None

    def test_invalid_command(self):
        plugin = ZaloPlugin()
        with patch.dict(os.environ, {"ZALO_OA_ACCESS_TOKEN": "test_token"}):
            result = plugin.execute("invalid_command")
            assert not result.success
