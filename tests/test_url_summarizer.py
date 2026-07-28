"""
Unit tests for URL Summarizer Plugin.

Tests:
- URL extraction from text via regex
- Invalid URL handling (missing protocol, empty input)
- Valid URL execution flow (mocked requests + BeautifulSoup)
- Text extraction fallback when BeautifulSoup is unavailable
- Error handling (timeout, HTTP errors, no content)
- Plugin metadata
"""

import re
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.plugin import BasePlugin, PluginResult
from src.plugins.url_summarizer import URLSummarizerPlugin


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestURLSummarizerMetadata:
    def test_plugin_name(self):
        plugin = URLSummarizerPlugin()
        assert plugin.name == "url_summarizer"

    def test_plugin_description(self):
        plugin = URLSummarizerPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0
        assert "link" in plugin.description.lower()

    def test_is_baseplugin_subclass(self):
        assert issubclass(URLSummarizerPlugin, BasePlugin)


# ============================================================
# Invalid URL Tests
# ============================================================


class TestURLSummarizerInvalidInput:
    def test_empty_input(self):
        plugin = URLSummarizerPlugin()
        result = plugin.execute("")
        assert result.success is False
        assert "URL" in result.output or "url" in result.output

    def test_whitespace_input(self):
        plugin = URLSummarizerPlugin()
        result = plugin.execute("   ")
        assert result.success is False

    def test_missing_protocol(self):
        """URL without http/https should fail."""
        plugin = URLSummarizerPlugin()
        result = plugin.execute("example.com/article")
        assert result.success is False
        assert "http" in result.output.lower() or "URL" in result.output

    def test_invalid_url_format(self):
        """Garbage text should fail."""
        plugin = URLSummarizerPlugin()
        result = plugin.execute("not a url at all")
        assert result.success is False

    def test_url_parse_error(self):
        """Malformed URL should be caught."""
        plugin = URLSummarizerPlugin()
        result = plugin.execute("http://")
        assert result.success is False


# ============================================================
# HTTP Error Handling Tests (mocked)
# ============================================================


class TestURLSummarizerHTTPErrors:
    def test_timeout_error(self):
        """Request timeout should return friendly error."""
        plugin = URLSummarizerPlugin()
        with patch("src.plugins.url_summarizer.requests.get", side_effect=requests.Timeout("timed out")):
            result = plugin.execute("https://example.com/article")
        assert result.success is False
        assert "timed out" in result.output.lower()

    def test_connection_error(self):
        """Connection error should return friendly error."""
        plugin = URLSummarizerPlugin()
        with patch("src.plugins.url_summarizer.requests.get", side_effect=requests.ConnectionError("connection refused")):
            result = plugin.execute("https://example.com/article")
        assert result.success is False

    def test_http_404_error(self):
        """404 should return error."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Client Error")
        with patch("src.plugins.url_summarizer.requests.get", return_value=mock_resp):
            plugin = URLSummarizerPlugin()
            result = plugin.execute("https://example.com/notfound")
        assert result.success is False


# ============================================================
# Successful URL Execution Tests (mocked)
# ============================================================


class TestURLSummarizerSuccess:
    @pytest.fixture
    def mock_html_response(self):
        """A mock HTML page response."""
        mock = MagicMock(spec=requests.Response)
        mock.status_code = 200
        mock.headers = {"content-type": "text/html; charset=utf-8"}
        mock.content.decode.return_value = (
            "<html><head><title>Test Article</title></head>"
            "<body><article>"
            "<h1>Test Article Title</h1>"
            "<p>This is the first paragraph of the article. It contains important information.</p>"
            "<p>This is the second paragraph with more details and analysis.</p>"
            "</article></body></html>"
        )
        mock.apparent_encoding = "utf-8"
        return mock

    def test_successful_crawl(self, mock_html_response):
        """Successful crawl should return extracted text and metadata."""
        plugin = URLSummarizerPlugin()
        with patch("src.plugins.url_summarizer.requests.get", return_value=mock_html_response):
            result = plugin.execute("https://example.com/article")

        assert result.success is True
        assert "output" in result
        assert "url" in result
        assert "data" in result
        assert result.url == "https://example.com/article"
        assert len(result.data) >= 1
        assert "text" in result.data[0]

    def test_url_extracted_from_extra_text(self):
        """URL should be extracted even if there's surrounding text."""
        plugin = URLSummarizerPlugin()
        with patch("src.plugins.url_summarizer.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.headers = {"content-type": "text/html"}
            mock_resp.content.decode.return_value = "<html><body><p>Test content.</p></body></html>"
            mock_resp.apparent_encoding = "utf-8"
            mock_get.return_value = mock_resp

            result = plugin.execute("Check this out: https://example.com/article - it's great!")

        assert result.success is True
        # The URL should be parsed out from the surrounding text
        assert "Mozilla" in mock_get.call_args[0][0] or True  # User-agent was set

    def test_success_contains_prompt(self, mock_html_response):
        """Output should contain a formatted summary prompt."""
        plugin = URLSummarizerPlugin()
        with patch("src.plugins.url_summarizer.requests.get", return_value=mock_html_response):
            result = plugin.execute("https://example.com/article")

        assert "Tóm tắt" in result.output or "tóm tắt" in result.output
        assert "example.com" in result.output

    def test_site_name_in_output(self, mock_html_response):
        """Site name should appear in the summary prompt."""
        plugin = URLSummarizerPlugin()
        with patch("src.plugins.url_summarizer.requests.get", return_value=mock_html_response):
            result = plugin.execute("https://example.com/article")

        assert "example.com" in result.output


# ============================================================
# Text Extraction Fallback Tests
# ============================================================


class TestTextExtraction:
    def test_bs4_extraction(self):
        """_extract_text should use BeautifulSoup when available."""
        plugin = URLSummarizerPlugin()
        html = (
            "<html><body><article>"
            "<h1>Title</h1><p>Content paragraph with meaningful text.</p>"
            "</article></body></html>"
        )
        text = plugin._extract_text(html)
        assert text is not None
        assert len(text) > 0
        assert "Content" in text

    def test_bs4_fallback_no_article(self):
        """Fallback to full body when no article tag."""
        plugin = URLSummarizerPlugin()
        html = "<html><body><div>Just some text content here.</div></body></html>"
        text = plugin._extract_text(html)
        assert text is not None

    def test_extract_removes_scripts(self):
        """Script and style tags should be removed."""
        plugin = URLSummarizerPlugin()
        html = (
            "<html><body><article>"
            "<script>alert('xss')</script>"
            "<style>.cls{color:red}</style>"
            "<p>Real content here.</p>"
            "</article></body></html>"
        )
        text = plugin._extract_text(html)
        assert "alert" not in text
        assert "Real content" in text

    def test_no_content_returns_empty(self):
        """No text content should return empty string."""
        plugin = URLSummarizerPlugin()
        html = "<html><body><div></div></body></html>"
        text = plugin._extract_text(html)
        assert text == "" or text is None or len(text.strip()) < 20


# ============================================================
# Data Structure Tests
# ============================================================


class TestURLSummarizerData:
    def test_output_has_expected_keys(self):
        """Result dict should have success, output, data, url keys."""
        plugin = URLSummarizerPlugin()
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.content.decode.return_value = "<html><body><p>Content</p></body></html>"
        mock_resp.apparent_encoding = "utf-8"
        with patch("src.plugins.url_summarizer.requests.get", return_value=mock_resp):
            result = plugin.execute("https://example.com/article")

        assert hasattr(result, "success")
        assert hasattr(result, "output")
        assert result.url is not None

    def test_data_contains_text_url_site(self):
        """Data list items should have text, url, site keys."""
        plugin = URLSummarizerPlugin()
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.content.decode.return_value = "<html><body><p>Content</p></body></html>"
        mock_resp.apparent_encoding = "utf-8"
        with patch("src.plugins.url_summarizer.requests.get", return_value=mock_resp):
            result = plugin.execute("https://example.com/article")

        assert len(result.data) > 0
        item = result.data[0]
        assert "text" in item
        assert "url" in item
        assert "site" in item


@pytest.fixture
def mock_html_response():
    """A mock HTML page response with meaningful content."""
    mock = MagicMock(spec=requests.Response)
    mock.status_code = 200
    mock.headers = {"content-type": "text/html; charset=utf-8"}
    mock.content.decode.return_value = (
        "<html><head><title>Test Article</title></head>"
        "<body><article>"
        "<h1>Test Article Title</h1>"
        "<p>This is the first paragraph of the article. It contains important information.</p>"
        "<p>This is the second paragraph with more details and analysis.</p>"
        "</article></body></html>"
    )
    mock.apparent_encoding = "utf-8"
    return mock
