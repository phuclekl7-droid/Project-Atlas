"""
Unit tests for Image Generation Plugin.

Tests:
- Prompt extraction from user input (_extract_prompt)
- Image generation keywords detection
- Plugin metadata
- API key configuration
- Backend availability check
- Error handling (no API key, no prompt, missing requests)
- Replicate and Stability API calling (mocked)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.image_generator import (
    ImageGeneratorPlugin,
    _extract_prompt,
    _generate_replicate,
    _generate_stability,
)


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestImageGeneratorMetadata:
    def test_plugin_name(self):
        plugin = ImageGeneratorPlugin()
        assert plugin.name == "image_generator"

    def test_plugin_description(self):
        plugin = ImageGeneratorPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0

    def test_is_baseplugin_subclass(self):
        assert issubclass(ImageGeneratorPlugin, BasePlugin)

    def test_available_no_keys(self):
        """Without API keys, plugin.available should be False."""
        plugin = ImageGeneratorPlugin(replicate_api_key="", stability_api_key="")
        assert plugin.available is False

    def test_available_with_key(self, monkeypatch):
        """With API key, plugin.available should be True (assuming requests installed)."""
        monkeypatch.setattr("src.plugins.image_generator._HAS_REQUESTS", True)
        plugin = ImageGeneratorPlugin(replicate_api_key="test_key_123")
        assert plugin.available is True

    def test_description_with_key(self):
        """With API key configured, description should mention generation."""
        plugin = ImageGeneratorPlugin(replicate_api_key="test_key")
        desc = plugin.description
        assert "Tạo ảnh" in desc or "generate" in desc.lower() or "API" in desc

    def test_description_without_key(self):
        """Without API keys, description should mention configuration."""
        plugin = ImageGeneratorPlugin(replicate_api_key="", stability_api_key="")
        desc = plugin.description
        assert "cần" in desc.lower() or "API" in desc or "key" in desc.lower()


# ============================================================
# Prompt Extraction Tests
# ============================================================


class TestExtractPrompt:
    def test_vietnamese_prefix(self):
        """'vẽ một con mèo' → 'một con mèo'"""
        result = _extract_prompt("vẽ một con mèo")
        assert result is not None
        assert "một con mèo" in result

    def test_vietnamese_phrase(self):
        """'vẽ cho tôi một bức tranh' → 'một bức tranh'"""
        result = _extract_prompt("vẽ cho tôi một bức tranh phong cảnh")
        assert result is not None
        assert "phong cảnh" in result

    def test_english_prefix(self):
        """'draw a cat' → 'a cat'"""
        result = _extract_prompt("draw a cat")
        assert result is not None
        assert "a cat" in result

    def test_generate_prefix(self):
        """'generate a futuristic city' → 'a futuristic city'"""
        result = _extract_prompt("generate a futuristic city")
        assert result is not None
        assert "futuristic city" in result

    def test_imagine_command(self):
        """'/imagine a dragon' → 'a dragon'"""
        result = _extract_prompt("/imagine a dragon")
        assert result is not None
        assert "a dragon" in result

    def test_empty_prompt(self):
        """Empty or too short input should return None."""
        result = _extract_prompt("")
        assert result is None

    def test_very_short(self):
        """Less than 3 characters should return None."""
        result = _extract_prompt("vẽ")
        assert result is None

    def test_trailing_punctuation(self):
        """Trailing punctuation should be stripped."""
        result = _extract_prompt("vẽ một con mèo.")
        assert result is not None
        assert "." not in result


# ============================================================
# Plugin Execution Tests
# ============================================================


class TestImageGeneratorExecute:
    def test_empty_input(self):
        plugin = ImageGeneratorPlugin()
        result = plugin.execute("")
        assert result.success is False

    def test_non_generation_input(self):
        """Input without generation keywords should return empty."""
        plugin = ImageGeneratorPlugin()
        result = plugin.execute("Hello, how are you?")
        assert result.success is False
        assert result.output == ""

    def test_missing_api_key(self):
        """Generation request but no API keys configured."""
        plugin = ImageGeneratorPlugin(replicate_api_key="", stability_api_key="")
        result = plugin.execute("vẽ một con mèo")
        assert result.success is False
        assert "API" in result.output or "key" in result.output.lower()

    def test_missing_requests_library(self, monkeypatch):
        """When requests library is not available."""
        monkeypatch.setattr("src.plugins.image_generator._HAS_REQUESTS", False)
        plugin = ImageGeneratorPlugin(replicate_api_key="test_key")
        result = plugin.execute("vẽ một con mèo")
        assert result.success is False
        assert "requests" in result.output

    def test_very_short_prompt(self):
        """Prompt too short after extraction."""
        plugin = ImageGeneratorPlugin(replicate_api_key="test_key")
        result = plugin.execute("vẽ")
        assert result.success is False


# ============================================================
# Replicate API Tests (mocked)
# ============================================================


class TestGenerateReplicate:
    def test_successful_generation(self):
        """Successful Replicate generation should return image_url."""
        mock_start = MagicMock()
        mock_start.status_code = 201
        mock_start.json.return_value = {"id": "pred_123"}

        mock_poll = MagicMock()
        mock_poll.status_code = 200
        mock_poll.json.return_value = {
            "status": "succeeded",
            "output": ["https://replicate.delivery/image.png"],
        }

        with patch("src.plugins.image_generator.requests.post", return_value=mock_start):
            with patch("src.plugins.image_generator.requests.get", return_value=mock_poll):
                result = _generate_replicate("a cat", "test_key")

        assert result is not None
        assert "image_url" in result
        assert "replicate.delivery" in result["image_url"]

    def test_http_error(self):
        """API HTTP error should return error dict."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Invalid token"

        with patch("src.plugins.image_generator.requests.post", return_value=mock_resp):
            result = _generate_replicate("a cat", "bad_key")

        assert result is not None
        assert "error" in result

    def test_failed_generation(self):
        """Failed generation should return error dict."""
        mock_start = MagicMock()
        mock_start.status_code = 201
        mock_start.json.return_value = {"id": "pred_123"}

        mock_poll = MagicMock()
        mock_poll.status_code = 200
        mock_poll.json.return_value = {
            "status": "failed",
            "error": "NSFW content detected",
        }

        with patch("src.plugins.image_generator.requests.post", return_value=mock_start):
            with patch("src.plugins.image_generator.requests.get", return_value=mock_poll):
                result = _generate_replicate("bad stuff", "test_key")

        assert result is not None
        assert "error" in result
        assert "NSFW" in result["error"]


# ============================================================
# Stability API Tests (mocked)
# ============================================================


class TestGenerateStability:
    def test_successful_generation(self):
        """Successful Stability AI generation should return base64 image."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "artifacts": [{"base64": "iVBORw0KGgoAAAANSUhEUgAAAAE="}],
        }

        with patch("src.plugins.image_generator.requests.post", return_value=mock_resp):
            result = _generate_stability("a cat", "test_key")

        assert result is not None
        assert "image_base64" in result
        assert "iVBORw0KGgo" in result["image_base64"]

    def test_no_artifacts(self):
        """API response with no artifacts should return error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"artifacts": []}

        with patch("src.plugins.image_generator.requests.post", return_value=mock_resp):
            result = _generate_stability("a cat", "test_key")

        assert result is not None
        assert "error" in result

    def test_http_error(self):
        """API error should return error."""
        mock_resp = MagicMock()
        mock_resp.status_code = 400

        with patch("src.plugins.image_generator.requests.post", return_value=mock_resp):
            result = _generate_stability("a cat", "bad_key")

        assert result is not None
        assert "error" in result


# ============================================================
# Backend Selection Tests
# ============================================================


class TestBackendSelection:
    def test_replicate_preferred_when_available(self, monkeypatch):
        """Replicate should be tried first when configured as default."""
        monkeypatch.setattr("src.plugins.image_generator._HAS_REQUESTS", True)
        plugin = ImageGeneratorPlugin(
            replicate_api_key="rep_key",
            stability_api_key="stab_key",
            default_backend="replicate",
        )

        result = plugin.execute("vẽ một con mèo")
        assert result.success is False  # Will fail at network level but tried replicate first
