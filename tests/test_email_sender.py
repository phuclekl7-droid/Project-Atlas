"""
Tests for Feature #30: Gmail / Email Sender Plugin.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.plugins.email_sender import (
    EmailSenderPlugin,
    EmailMessage,
    EmailConfig,
    _parse_email_input,
    _send_email,
)


class TestParseEmailInput:
    """Tests for email input parsing."""

    def test_parse_full_email(self):
        msg = _parse_email_input(
            "to:user@example.com subject:Hello body:This is a test"
        )
        assert msg is not None
        assert msg.to == ["user@example.com"]
        assert msg.subject == "Hello"
        assert msg.body == "This is a test"

    def test_parse_multiple_recipients(self):
        msg = _parse_email_input(
            "to:a@b.com, c@d.com subject:Meeting body:Let's meet"
        )
        assert msg is not None
        assert msg.to == ["a@b.com", "c@d.com"]

    def test_parse_with_cc(self):
        msg = _parse_email_input(
            "to:a@b.com cc:admin@b.com subject:Report body:Done"
        )
        assert msg is not None
        assert msg.to == ["a@b.com"]
        assert msg.cc == ["admin@b.com"]

    def test_parse_no_recipient(self):
        msg = _parse_email_input("subject:Hello body:Test")
        assert msg is None

    def test_empty_input(self):
        msg = _parse_email_input("")
        assert msg is None


class TestEmailSenderPlugin:
    """Tests for the EmailSenderPlugin class."""

    def test_empty_input(self):
        plugin = EmailSenderPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_no_recipient(self):
        plugin = EmailSenderPlugin()
        result = plugin.execute("subject:Hello body:Test")
        assert not result.success
        assert "địa chỉ người nhận" in result.error

    def test_no_subject(self):
        plugin = EmailSenderPlugin()
        result = plugin.execute("to:user@example.com body:Test")
        assert not result.success

    def test_no_body(self):
        plugin = EmailSenderPlugin()
        result = plugin.execute("to:user@example.com subject:Hello")
        assert not result.success

    def test_no_config(self):
        """Without EMAIL_USERNAME, should return config error."""
        plugin = EmailSenderPlugin()
        with patch.dict(os.environ, {}, clear=True):
            result = plugin.execute("to:user@example.com subject:Hi body:Test")
            assert not result.success
            assert "cấu hình" in result.error


class TestSendEmail:
    """Tests for _send_email function."""

    def test_send_success(self):
        config = EmailConfig(
            host="smtp.test.com", port=587,
            username="user@test.com", password="pass",
        )
        msg = EmailMessage(to=["a@b.com"], subject="Hi", body="Test")

        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__.return_value = instance
            error = _send_email(config, msg)
            assert error is None
            instance.sendmail.assert_called_once()

    def test_send_auth_failure(self):
        config = EmailConfig(
            host="smtp.test.com", port=587,
            username="user@test.com", password="wrong",
        )
        msg = EmailMessage(to=["a@b.com"], subject="Hi", body="Test")

        import smtplib
        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            instance.sendmail.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
            mock_smtp.return_value.__enter__.return_value = instance
            error = _send_email(config, msg)
            assert error is not None
            assert "authentication" in error.lower()
