"""
Unit tests for PDF Exporter (Export Chat to PDF).

Tests:
- export_chat_as_pdf_html returns valid HTML
- HTML contains doctype and html structure
- HTML includes session name and message count
- HTML renders message bubbles with correct roles
- _format_message creates proper bubble HTML
- get_export_stats returns correct counts
- export with empty messages
- Edge cases: long content, missing fields
"""

import pytest

from src.features.pdf_exporter import (
    export_chat_as_pdf_html,
    _format_message,
    _generate_chat_html,
    count_export_messages,
    get_export_stats,
)


class TestFormatMessage:
    def test_user_message(self):
        html = _format_message("user", "Hello!", index=0)
        assert "bubble-user" in html
        assert "Hello!" in html
        assert "👤" in html
        assert "Bạn" in html

    def test_assistant_message(self):
        html = _format_message("assistant", "Hi there!", index=0)
        assert "bubble-assistant" in html
        assert "Hi there!" in html
        assert "🤖" in html
        assert "AI" in html

    def test_with_provider(self):
        html = _format_message("assistant", "Hello", provider="openai", index=0)
        assert "openai" in html.lower() or "openai" in html

    def test_escapes_content(self):
        html = _format_message("user", "<script>alert('xss')</script>", index=0)
        assert "<script>" not in html or "&lt;" in html

    def test_long_content(self):
        content = "Hello world. " * 100
        html = _format_message("user", content, index=0)
        assert len(html) > len(content)


class TestExportChatAsPdfHtml:
    @pytest.fixture
    def sample_messages(self):
        return [
            {"role": "user", "content": "Hello, what is AI?", "provider": ""},
            {"role": "assistant", "content": "AI stands for Artificial Intelligence.", "provider": "openai"},
            {"role": "user", "content": "Tell me more!", "provider": ""},
            {"role": "assistant", "content": "Machine learning is a subset of AI.", "provider": "openai"},
        ]

    def test_returns_html(self):
        html = export_chat_as_pdf_html("Test Session", [])
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_contains_session_name(self, sample_messages):
        html = export_chat_as_pdf_html("AI Chat", sample_messages)
        assert "AI Chat" in html

    def test_contains_message_content(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages)
        assert "Hello, what is AI?" in html
        assert "Machine learning" in html

    def test_contains_message_count(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages)
        assert "4" in html  # 4 messages

    def test_metadata_header(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages, include_metadata=True)
        assert "tin nhắn" in html

    def test_no_metadata(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages, include_metadata=False)
        # Still fine, metadata is optional
        assert "Project Atlas" in html

    def test_empty_messages(self):
        html = export_chat_as_pdf_html("Empty Session", [])
        assert "Empty Session" in html
        assert "0" in html or "messages" in html

    def test_chat_bubbles_styled(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages)
        assert "bubble" in html
        assert "bubble-user" in html
        assert "bubble-assistant" in html

    def test_css_print_media(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages)
        assert "@media print" in html

    def test_has_page_styles(self, sample_messages):
        html = export_chat_as_pdf_html("Test", sample_messages)
        assert "@page" in html
        assert "font-family" in html

    def test_missing_fields(self):
        """Messages with missing fields should not crash."""
        messages = [
            {"role": "user"},  # No content
            {},  # Empty dict
            {"role": "assistant", "content": "Hello"},
        ]
        html = export_chat_as_pdf_html("Test", messages)
        assert "Hello" in html


class TestCountExportMessages:
    def test_count(self):
        msgs = [{"role": "user"}, {"role": "assistant"}]
        assert count_export_messages(msgs) == 2

    def test_empty(self):
        assert count_export_messages([]) == 0


class TestGetExportStats:
    def test_stats(self):
        msgs = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]
        stats = get_export_stats(msgs)
        assert stats["total"] == 3
        assert stats["user_messages"] == 2
        assert stats["assistant_messages"] == 1
        assert stats["total_chars"] > 0

    def test_empty(self):
        stats = get_export_stats([])
        assert stats["total"] == 0
        assert stats["total_chars"] == 0
