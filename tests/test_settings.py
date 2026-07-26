"""
Unit tests for the Settings module.

Tests:
- Default values for all fields
- Environment variable overrides
- .env file loading
- config.json loading
- Priority chain: env var > .env > config.json > default
- Validation (invalid provider, missing API keys)
- _safe_int error handling
- to_dict (safe export without secrets)
"""

import json
import os

import pytest

from src.core import ConfigurationError
from src.settings import (
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_GEMINI,
    SUPPORTED_PROVIDERS,
    Settings,
    _safe_int,
    load_settings,
)


# ============================================================
# Default Values
# ============================================================


class TestSettingsDefaults:
    def test_default_provider_is_mock(self):
        """Default model provider should be 'mock'."""
        s = Settings()
        assert s.model_provider == PROVIDER_MOCK

    def test_default_ollama_url(self):
        """Default Ollama URL should be localhost:11434."""
        s = Settings()
        assert s.ollama_url == "http://localhost:11434"

    def test_default_ollama_model(self):
        """Default Ollama model should be llama3.2:1b."""
        s = Settings()
        assert s.ollama_model == "llama3.2:1b"

    def test_default_log_level(self):
        """Default log level should be INFO."""
        s = Settings()
        assert s.log_level == "INFO"

    def test_default_max_context_messages(self):
        """Default max context messages should be 10."""
        s = Settings()
        assert s.max_context_messages == 10

    def test_default_memory_path_ends_with_db(self):
        """Default memory path should end with .db."""
        s = Settings()
        assert s.memory_path.endswith("memory.db")

    def test_default_openai_key_is_empty(self):
        """Default OpenAI API key should be empty string."""
        s = Settings()
        assert s.openai_api_key == ""


# ============================================================
# Validation
# ============================================================


class TestSettingsValidation:
    def test_mock_provider_valid(self):
        """Mock provider should pass validation."""
        s = Settings(model_provider=PROVIDER_MOCK)
        s.validate()  # Should not raise

    def test_ollama_provider_valid(self):
        """Ollama provider should pass validation (no API key needed)."""
        s = Settings(model_provider=PROVIDER_OLLAMA)
        s.validate()  # Should not raise

    def test_openai_without_key_raises(self):
        """OpenAI provider without API key should raise ConfigurationError."""
        s = Settings(model_provider=PROVIDER_OPENAI, openai_api_key="")
        with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
            s.validate()

    def test_openai_with_key_valid(self):
        """OpenAI provider with API key should pass validation."""
        s = Settings(model_provider=PROVIDER_OPENAI, openai_api_key="sk-test-key")
        s.validate()  # Should not raise

    def test_gemini_without_key_raises(self):
        """Gemini provider without API key should raise ConfigurationError."""
        s = Settings(model_provider=PROVIDER_GEMINI, gemini_api_key="")
        with pytest.raises(ConfigurationError, match="GEMINI_API_KEY"):
            s.validate()

    def test_gemini_with_key_valid(self):
        """Gemini provider with API key should pass validation."""
        s = Settings(model_provider=PROVIDER_GEMINI, gemini_api_key="ai-test-key")
        s.validate()  # Should not raise

    def test_invalid_provider_raises(self):
        """An unsupported provider should raise ConfigurationError."""
        s = Settings(model_provider="nonexistent")
        with pytest.raises(ConfigurationError, match="nonexistent"):
            s.validate()


# ============================================================
# to_dict (safe export)
# ============================================================


class TestSettingsToDict:
    def test_to_dict_contains_expected_keys(self):
        """to_dict should contain all public config fields."""
        s = Settings()
        d = s.to_dict()
        assert "model_provider" in d
        assert "ollama_url" in d
        assert "log_level" in d
        assert "memory_path" in d

    def test_to_dict_does_not_expose_secrets(self):
        """to_dict should NOT include API keys (safety)."""
        s = Settings(openai_api_key="sk-secret", gemini_api_key="ai-secret")
        d = s.to_dict()
        assert "openai_api_key" not in d
        assert "gemini_api_key" not in d

    def test_to_dict_has_max_context_messages(self):
        """to_dict should include max_context_messages."""
        s = Settings(max_context_messages=20)
        d = s.to_dict()
        assert d["max_context_messages"] == 20


# ============================================================
# load_settings with priority chain
# ============================================================


class TestLoadSettings:
    def test_load_defaults(self, tmp_path):
        """load_settings should return defaults when no config files exist."""
        env_path = tmp_path / ".env"
        config_path = tmp_path / "config.json"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.model_provider == PROVIDER_MOCK
        assert s.max_context_messages == 10

    def test_load_from_env_var(self, tmp_path, monkeypatch):
        """Environment variable should override default."""
        monkeypatch.setenv("MODEL_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_MODEL", "mistral")
        env_path = tmp_path / ".env"
        config_path = tmp_path / "config.json"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.model_provider == PROVIDER_OLLAMA
        assert s.ollama_model == "mistral"

    def test_load_from_dotenv_file(self, tmp_path):
        """.env file values should be loaded when no env var is set."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            'MODEL_PROVIDER=ollama\n'
            'OLLAMA_MODEL=llama3.2\n'
        )
        config_path = tmp_path / "config.json"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.model_provider == PROVIDER_OLLAMA
        assert s.ollama_model == "llama3.2"

    def test_env_var_overrides_dotenv(self, tmp_path, monkeypatch):
        """Existing env var should override .env file value."""
        monkeypatch.setenv("MODEL_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        env_path = tmp_path / ".env"
        env_path.write_text('MODEL_PROVIDER=ollama\n')
        config_path = tmp_path / "config.json"
        s = load_settings(env_path=env_path, config_path=config_path)
        # The env var should win over .env
        assert s.model_provider == PROVIDER_OPENAI

    def test_load_from_config_json(self, tmp_path):
        """config.json values should be used when no env var or .env."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "model_provider": "ollama",
            "ollama_model": "llama3.2-vision",
        }))
        env_path = tmp_path / ".env"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.model_provider == PROVIDER_OLLAMA
        assert s.ollama_model == "llama3.2-vision"

    def test_json_config_ignored_when_env_exists(self, tmp_path, monkeypatch):
        """config.json should be ignored if env var or .env already sets the value."""
        monkeypatch.setenv("MODEL_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"model_provider": "ollama"}))
        env_path = tmp_path / ".env"
        s = load_settings(env_path=env_path, config_path=config_path)
        # Env var should win
        assert s.model_provider == PROVIDER_OPENAI

    def test_full_priority_chain(self, tmp_path):
        """Test complete priority: env > .env > config.json > default."""
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({
            "model_provider": "gemini",
            "gemini_api_key": "ai-from-json",
            "ollama_model": "from-json",
        }))
        env_path = tmp_path / ".env"
        env_path.write_text(
            'MODEL_PROVIDER=ollama\n'
            'OLLAMA_MODEL=from-dotenv\n'
        )
        s = load_settings(env_path=env_path, config_path=config_path)
        # .env overrides config.json
        assert s.model_provider == PROVIDER_OLLAMA
        assert s.ollama_model == "from-dotenv"
        # config.json fills in missing values (gemini_api_key)
        assert s.gemini_api_key == "ai-from-json"

    def test_missing_config_file(self, tmp_path):
        """Non-existent config files should not raise."""
        env_path = tmp_path / ".env"
        config_path = tmp_path / "nonexistent.json"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.model_provider == PROVIDER_MOCK

    def test_invalid_config_json(self, tmp_path):
        """Malformed config.json should not crash."""
        config_path = tmp_path / "config.json"
        config_path.write_text("not valid json {{{")
        env_path = tmp_path / ".env"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.model_provider == PROVIDER_MOCK

    def test_invalid_max_context_env_var_falls_back(self, tmp_path, monkeypatch):
        """Invalid MAX_CONTEXT_MESSAGES in env should fall back to default."""
        monkeypatch.setenv("MAX_CONTEXT_MESSAGES", "not-a-number")
        env_path = tmp_path / ".env"
        config_path = tmp_path / "config.json"
        s = load_settings(env_path=env_path, config_path=config_path)
        assert s.max_context_messages == 10  # Default value


# ============================================================
# _safe_int
# ============================================================


class TestSafeInt:
    def test_valid_integer_string(self):
        """Valid integer string should parse correctly."""
        assert _safe_int("42", 0) == 42
        assert _safe_int("0", 0) == 0
        assert _safe_int("-5", 0) == -5

    def test_invalid_string_falls_back(self):
        """Invalid string should fall back to default."""
        assert _safe_int("abc", 10) == 10
        assert _safe_int("", 5) == 5

    def test_none_falls_back(self):
        """None should fall back to default."""
        assert _safe_int(None, 7) == 7  # type: ignore

    def test_float_string_falls_back(self):
        """Float string should fall back (not a valid int)."""
        assert _safe_int("3.14", 1) == 1

    def test_whitespace_falls_back(self):
        """Whitespace-only string should fall back."""
        assert _safe_int("   ", 99) == 99


# ============================================================
# Settings repr
# ============================================================


class TestSettingsRepr:
    def test_repr_contains_provider(self):
        """__repr__ should mention the model provider."""
        s = Settings()
        r = repr(s)
        assert PROVIDER_MOCK in r

    def test_repr_masks_api_keys(self):
        """__repr__ should mask API keys for safety."""
        s = Settings(openai_api_key="sk-secret-123")
        r = repr(s)
        assert "***" in r
        assert "sk-secret-123" not in r
