"""Tests for Google Search Plugin (Feature 22)."""

import pytest
from src.plugins.google_search import GoogleSearchPlugin, _extract_query


class TestExtractQuery:
    """Test search query extraction."""

    def test_simple_query(self):
        result = _extract_query("search Python programming")
        assert result == "Python programming"

    def test_vietnamese_query(self):
        result = _extract_query("tìm kiếm Python là gì")
        assert result == "Python là gì"

    def test_google_prefix(self):
        result = _extract_query("google Python")
        assert result == "Python"

    def test_slash_google(self):
        result = _extract_query("/google Python tutorials")
        assert result == "Python tutorials"

    def test_short_query_becomes_none(self):
        result = _extract_query("a")
        assert result is None

    def test_search_with_quotes(self):
        result = _extract_query('search "hello world"')
        assert result == '"hello world"'

    def test_clean_query(self):
        result = _extract_query("search what is Python?")
        assert result is not None


class TestGoogleSearchPlugin:
    """Test Google Search plugin behavior."""

    def test_plugin_name(self):
        plugin = GoogleSearchPlugin()
        assert plugin.name == "google_search"

    def test_plugin_description(self):
        plugin = GoogleSearchPlugin()
        assert "google" in plugin.description.lower() or "tìm" in plugin.description.lower()

    def test_empty_input(self):
        plugin = GoogleSearchPlugin()
        result = plugin.execute("")
        assert result.success is False
        assert result.output == ""

    def test_no_search_keyword(self):
        """Input without search keyword returns empty."""
        plugin = GoogleSearchPlugin()
        result = plugin.execute("Hello, how are you?")
        assert result.success is False
        assert result.output == ""

    def test_no_api_key(self):
        """Search request without API key shows config message."""
        plugin = GoogleSearchPlugin(api_key="", cse_id="")
        result = plugin.execute("search Python")
        assert result.success is False

    def test_available_with_keys(self):
        plugin = GoogleSearchPlugin(api_key="test", cse_id="test")
        assert plugin.available is True

    def test_not_available_without_keys(self):
        plugin = GoogleSearchPlugin(api_key="", cse_id="")
        assert plugin.available is False
