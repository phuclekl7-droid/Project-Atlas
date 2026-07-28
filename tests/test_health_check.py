"""
Unit tests for Provider Health Check functionality.

Tests cover:
- MockModel.check_health() — always returns ok=True
- OllamaModel.check_health() — mocked GET /api/tags
- OpenAIModel.check_health() — mocked GET /v1/models
- GeminiModel.check_health() — mocked genai calls
- ModelRouter.check_all_providers() — returns list of all 4 providers
- Health cache invalidation
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.model_router import (
    PROVIDER_GEMINI,
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    GeminiModel,
    MockModel,
    ModelRouter,
    OllamaModel,
    OpenAIModel,
)
from src.settings import Settings


# ============================================================
# MockModel
# ============================================================


class TestMockModelHealth:
    def test_always_healthy(self, mock_settings):
        """MockModel.check_health should always return ok=True."""
        model = MockModel(mock_settings)
        result = model.check_health()
        assert result["provider"] == PROVIDER_MOCK
        assert result["ok"] is True
        assert result["error"] is None
        assert result["model"] == "mock-v1"
        assert result["latency_ms"] == 0.0


# ============================================================
# OllamaModel
# ============================================================


class TestOllamaModelHealth:
    def test_healthy(self, ollama_settings):
        """Ollama health passes when /api/tags returns 200."""
        model = OllamaModel(ollama_settings)
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"models": []}
            result = model.check_health()
            assert result["provider"] == PROVIDER_OLLAMA
            assert result["ok"] is True
            assert result["error"] is None

    def test_http_error(self, ollama_settings):
        """Ollama health fails when /api/tags returns non-200."""
        model = OllamaModel(ollama_settings)
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 500
            result = model.check_health()
            assert result["ok"] is False
            assert "HTTP 500" in result["error"]

    def test_connection_error(self, ollama_settings):
        """Ollama health fails gracefully on connection error."""
        model = OllamaModel(ollama_settings)
        with patch("requests.get", side_effect=requests.ConnectionError("Refused")):
            result = model.check_health()
            assert result["ok"] is False
            assert "Cannot connect" in result["error"]

    def test_timeout(self, ollama_settings):
        """Ollama health fails gracefully on timeout."""
        model = OllamaModel(ollama_settings)
        with patch("requests.get", side_effect=requests.Timeout("Timed out")):
            result = model.check_health()
            assert result["ok"] is False
            assert "timed out" in result["error"].lower()


# ============================================================
# OpenAIModel
# ============================================================


class TestOpenAIModelHealth:
    def test_healthy(self, openai_settings):
        """OpenAI health passes when /v1/models returns 200."""
        model = OpenAIModel(openai_settings)
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"data": [{"id": "gpt-4"}]}
            result = model.check_health()
            assert result["provider"] == PROVIDER_OPENAI
            assert result["ok"] is True
            assert result["error"] is None

    def test_missing_api_key(self):
        """OpenAI health fails when API key is not configured."""
        settings = Settings(model_provider=PROVIDER_OPENAI, openai_api_key="")
        model = OpenAIModel(settings)
        result = model.check_health()
        assert result["ok"] is False
        assert "API key not configured" in result["error"]

    def test_http_error(self, openai_settings):
        """OpenAI health fails on HTTP error."""
        model = OpenAIModel(openai_settings)
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 401
            result = model.check_health()
            assert result["ok"] is False
            assert "HTTP 401" in result["error"]

    def test_connection_error(self, openai_settings):
        """OpenAI health fails gracefully on connection error."""
        model = OpenAIModel(openai_settings)
        with patch("requests.get", side_effect=requests.ConnectionError("No route")):
            result = model.check_health()
            assert result["ok"] is False
            assert "Cannot connect" in result["error"]


# ============================================================
# GeminiModel
# ============================================================


class TestGeminiModelHealth:
    def test_healthy(self, gemini_settings):
        """Gemini health passes when genai responds."""
        model = GeminiModel(gemini_settings)
        mock_genai = MagicMock()
        model._genai = mock_genai
        result = model.check_health()
        assert result["provider"] == PROVIDER_GEMINI
        assert result["ok"] is True
        assert result["error"] is None

    def test_missing_api_key(self):
        """Gemini health fails when API key is not configured."""
        settings = Settings(model_provider=PROVIDER_GEMINI, gemini_api_key="")
        model = GeminiModel(settings)
        # Prevent _get_genai from raising ImportError
        mock_genai = MagicMock()
        model._genai = mock_genai
        result = model.check_health()
        assert result["ok"] is False
        assert "API key not configured" in result["error"]

    def test_api_key_invalid(self, gemini_settings):
        """Gemini health fails gracefully on invalid API key."""
        model = GeminiModel(gemini_settings)
        mock_genai = MagicMock()
        # configure raises exception
        mock_genai.configure.side_effect = Exception("API_KEY_INVALID")
        model._genai = mock_genai
        result = model.check_health()
        assert result["ok"] is False
        assert "API key invalid" in result["error"] or "API_KEY" in result["error"]


# ============================================================
# ModelRouter — check_all_providers
# ============================================================


class TestModelRouterCheckAll:
    def test_returns_all_providers(self, mock_settings):
        """check_all_providers should return results for all 4 providers."""
        router = ModelRouter(mock_settings)
        results = router.check_all_providers(force=True)
        assert len(results) == 4
        providers = {r["provider"] for r in results}
        assert providers == {PROVIDER_MOCK, PROVIDER_OLLAMA, PROVIDER_OPENAI, PROVIDER_GEMINI}

    def test_mock_always_ok(self, mock_settings):
        """Mock result should always be ok=True."""
        router = ModelRouter(mock_settings)
        results = router.check_all_providers(force=True)
        mock_result = [r for r in results if r["provider"] == PROVIDER_MOCK][0]
        assert mock_result["ok"] is True

    def test_caching(self, mock_settings):
        """check_all_providers should cache results."""
        router = ModelRouter(mock_settings)
        # First call populates cache
        results1 = router.check_all_providers()
        # Second call should use cache (no errors expected for mock)
        results2 = router.check_all_providers()
        assert len(results2) == len(results1)
        assert router._health_cache_time > 0

    def test_force_refresh(self, mock_settings):
        """force=True should bypass cache."""
        router = ModelRouter(mock_settings)
        router.check_all_providers()  # Cache populated
        old_time = router._health_cache_time
        router.check_all_providers(force=True)
        assert router._health_cache_time >= old_time
