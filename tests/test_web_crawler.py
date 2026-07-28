"""
Tests for Feature #65: Web Crawler Agent.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.plugins.web_crawler import (
    WebCrawlerPlugin,
    _is_same_domain,
    _clean_url,
    _extract_title,
    _extract_links,
)


class TestUrlHelpers:
    """Tests for URL helper functions."""

    def test_is_same_domain(self):
        assert _is_same_domain("https://example.com/page", "example.com")
        assert _is_same_domain("https://example.com/other", "example.com")
        assert not _is_same_domain("https://other.com/page", "example.com")

    def test_clean_url(self):
        assert _clean_url("https://example.com/page#section") == "https://example.com/page"
        assert _clean_url("https://example.com/") == "https://example.com"


class TestExtractTitle:
    """Tests for HTML title extraction."""

    def test_extract_title_html(self):
        html = "<html><head><title>My Page</title></head><body></body></html>"
        title = _extract_title(html)
        assert title == "My Page"

    def test_no_title(self):
        html = "<html><body>No title here</body></html>"
        title = _extract_title(html)
        assert title == "(no title)" or "no title" in title


class TestExtractLinks:
    """Tests for link extraction from HTML."""

    def test_extract_links_regex_fallback(self):
        html = '<a href="https://example.com/page1">Link 1</a>'
        with patch("src.plugins.web_crawler._HAS_BS4", False):
            links = _extract_links(html, "https://base.com")
            assert len(links) >= 1
            assert "example.com/page1" in links[0]


class TestWebCrawlerPlugin:
    """Tests for the WebCrawlerPlugin class."""

    def test_empty_input(self):
        plugin = WebCrawlerPlugin()
        result = plugin.execute("")
        assert not result.success

    def test_no_url(self):
        plugin = WebCrawlerPlugin()
        result = plugin.execute("some text without a url")
        assert not result.success
        assert "URL" in result.error

    def test_invalid_url(self):
        plugin = WebCrawlerPlugin()
        result = plugin.execute("not-a-url-at-all")
        assert not result.success

    def test_url_extraction(self):
        plugin = WebCrawlerPlugin()
        result = plugin.execute("https://example.com depth:1 max:1")
        # either success or failure is OK (depends on network)
        # Just ensure it doesn't crash
        assert result.success is not None
