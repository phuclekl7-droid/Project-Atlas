"""
Unit tests for the Model Router module.

Tests:
- MockModel: response types, context handling, latency simulation
- OllamaModel: _build_url, _build_messages, successful chat, connection error (mocked)
- OpenAIModel: _build_messages, successful chat, missing API key, connection error (mocked)
- ModelRouter: factory selection, generate with/without context, invalid provider, empty prompt
"""

import time
from unittest.mock import patch

import pytest
import requests

from src.core import AssistantError, ConfigurationError, ModelConnectionError
from src.model_router import (
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    BaseModel,
    MockModel,
    ModelResponse,
    ModelRouter,
    OllamaModel,
    OpenAIModel,
)
from src.settings import Settings


# ============================================================
# MockModel Tests
# ============================================================


class TestMockModel:
    def test_init(self, mock_settings):
        """MockModel should initialize with model name 'mock-v1'."""
        model = MockModel(mock_settings)
        assert model.model_name == "mock-v1"
        assert isinstance(model, BaseModel)

    def test_greeting_response(self, mock_settings):
        """MockModel should return a greeting for 'hello'."""
        model = MockModel(mock_settings)
        response = model.generate("Hello! How are you?")
        assert isinstance(response, ModelResponse)
        assert response.provider == PROVIDER_MOCK
        assert "Xin chào" in response.text or "chào" in response.text

    def test_greeting_response_hi(self, mock_settings):
        """MockModel should return a greeting for 'hi'."""
        model = MockModel(mock_settings)
        response = model.generate("hi there")
        assert "Xin chào" in response.text

    def test_greeting_response_vietnamese(self, mock_settings):
        """MockModel should return a greeting for Vietnamese 'xin chào'."""
        model = MockModel(mock_settings)
        response = model.generate("Xin chào bạn")
        assert "Xin chào" in response.text

    def test_who_are_you_response(self, mock_settings):
        """MockModel should answer 'who are you'."""
        model = MockModel(mock_settings)
        response = model.generate("Who are you?")
        assert "Personal AI Assistant" in response.text

    def test_who_are_you_vietnamese(self, mock_settings):
        """MockModel should answer 'bạn là ai'."""
        model = MockModel(mock_settings)
        response = model.generate("Bạn là ai?")
        assert "trợ lý AI" in response.text

    def test_help_response(self, mock_settings):
        """MockModel should return help for 'help'."""
        model = MockModel(mock_settings)
        response = model.generate("help me please")
        assert "giúp" in response.text.lower()

    def test_help_vietnamese(self, mock_settings):
        """MockModel should return help for 'giúp'."""
        model = MockModel(mock_settings)
        response = model.generate("giúp tôi với")
        assert "giúp" in response.text.lower()

    def test_fallback_response(self, mock_settings):
        """MockModel should return a generic mock response for unknown prompts."""
        model = MockModel(mock_settings)
        response = model.generate("What is the weather like today?")
        assert "Mock Response" in response.text or "mô phỏng" in response.text

    def test_context_count_displayed(self, mock_settings):
        """MockModel should mention context count when context is provided."""
        model = MockModel(mock_settings)
        context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        response = model.generate("Tell me more", context=context)
        # Should mention the number of context messages
        assert "2" in response.text or "tin nhắn" in response.text

    def test_empty_context(self, mock_settings):
        """MockModel should work with empty context list."""
        model = MockModel(mock_settings)
        response = model.generate("Hello", context=[])
        assert "0" in response.text or "chào" in response.text

    def test_latency_value(self, mock_settings):
        """MockModel response should include latency."""
        model = MockModel(mock_settings)
        response = model.generate("test")
        assert response.latency_ms > 0

    def test_repr(self, mock_settings):
        """__repr__ should include class name and model."""
        model = MockModel(mock_settings)
        r = repr(model)
        assert "MockModel" in r
        assert "mock-v1" in r


# ============================================================
# OllamaModel Tests (mocked requests)
# ============================================================


class TestOllamaModel:
    def test_init(self, ollama_settings):
        """OllamaModel should initialize with the configured model name."""
        model = OllamaModel(ollama_settings)
        assert model.model_name == "llama3.2:1b"

    def test_build_url(self, ollama_settings):
        """_build_url should construct proper Ollama API URLs."""
        model = OllamaModel(ollama_settings)
        url = model._build_url("chat")
        assert url == "http://localhost:11434/api/chat"
        url2 = model._build_url("/chat")
        assert url2 == "http://localhost:11434/api/chat"

    def test_build_messages_no_context(self, ollama_settings):
        """_build_messages without context should just wrap the prompt."""
        model = OllamaModel(ollama_settings)
        messages = model._build_messages("Hello", context=None)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_build_messages_with_context(self, ollama_settings):
        """_build_messages with context should append to history."""
        model = OllamaModel(ollama_settings)
        context = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        messages = model._build_messages("New question", context=context)
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Previous question"
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "New question"

    def test_build_messages_empty_context(self, ollama_settings):
        """_build_messages with empty list should behave like no context."""
        model = OllamaModel(ollama_settings)
        messages = model._build_messages("Hello", context=[])
        assert len(messages) == 1

    def test_successful_chat(self, ollama_settings, mock_ollama_chat_response):
        """Successful Ollama call should return ModelResponse with text."""
        model = OllamaModel(ollama_settings)
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_ollama_chat_response
            mock_post.return_value.text = str(mock_ollama_chat_response)

            response = model.generate("Hello!")
            assert isinstance(response, ModelResponse)
            assert response.provider == PROVIDER_OLLAMA
            assert response.text == mock_ollama_chat_response["message"]["content"]
            assert response.latency_ms >= 0

    def test_connection_error(self, ollama_settings):
        """ConnectionError should be wrapped in ModelConnectionError."""
        model = OllamaModel(ollama_settings)
        with patch("requests.post", side_effect=requests.ConnectionError("Connection refused")):
            with pytest.raises(ModelConnectionError, match="Cannot connect to Ollama"):
                model.generate("Hello")

    def test_timeout_error(self, ollama_settings):
        """Timeout should be wrapped in ModelConnectionError."""
        model = OllamaModel(ollama_settings)
        with patch("requests.post", side_effect=requests.Timeout("Timed out")):
            with pytest.raises(ModelConnectionError, match="timed out"):
                model.generate("Hello")

    def test_http_error(self, ollama_settings, mock_ollama_error_response):
        """HTTP error (e.g. 404) should raise ModelConnectionError."""
        model = OllamaModel(ollama_settings)
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 404
            mock_post.return_value.text = str(mock_ollama_error_response)

            with pytest.raises(ModelConnectionError, match="HTTP 404"):
                model.generate("Hello")


# ============================================================
# OpenAIModel Tests (mocked requests)
# ============================================================


class TestOpenAIModel:
    def test_init(self, openai_settings):
        """OpenAIModel should initialize with the configured model."""
        model = OpenAIModel(openai_settings)
        assert model.model_name == "gpt-4o-mini"

    def test_build_messages_no_context(self, openai_settings):
        """_build_messages without context."""
        model = OpenAIModel(openai_settings)
        messages = model._build_messages("Hello")
        assert len(messages) == 1

    def test_build_messages_with_context(self, openai_settings):
        """_build_messages with context should include history."""
        model = OpenAIModel(openai_settings)
        context = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
        ]
        messages = model._build_messages("Q2", context=context)
        assert len(messages) == 3

    def test_missing_api_key_raises(self):
        """OpenAIModel without API key should raise ConfigurationError."""
        settings = Settings(model_provider=PROVIDER_OPENAI, openai_api_key="")
        with pytest.raises(ConfigurationError, match="API key"):
            OpenAIModel(settings).generate("Hello")

    def test_successful_chat(self, openai_settings, mock_openai_chat_response):
        """Successful OpenAI call should return ModelResponse with text."""
        model = OpenAIModel(openai_settings)
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_openai_chat_response
            mock_post.return_value.text = str(mock_openai_chat_response)

            response = model.generate("Hello!")
            assert isinstance(response, ModelResponse)
            assert response.provider == PROVIDER_OPENAI
            assert response.text == mock_openai_chat_response["choices"][0]["message"]["content"]
            assert response.tokens_used == 22

    def test_connection_error(self, openai_settings):
        """ConnectionError should be wrapped in ModelConnectionError."""
        model = OpenAIModel(openai_settings)
        with patch("requests.post", side_effect=requests.ConnectionError("No route to host")):
            with pytest.raises(ModelConnectionError, match="Cannot connect to OpenAI"):
                model.generate("Hello")

    def test_http_error(self, openai_settings):
        """HTTP 401 should raise ModelConnectionError."""
        model = OpenAIModel(openai_settings)
        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 401
            mock_post.return_value.text = '{"error": "Invalid API key"}'

            with pytest.raises(ModelConnectionError, match="HTTP 401"):
                model.generate("Hello")


# ============================================================
# ModelRouter Tests
# ============================================================


class TestModelRouter:
    def test_init_with_mock(self, mock_settings):
        """ModelRouter should create a MockModel when provider is mock."""
        router = ModelRouter(mock_settings)
        assert isinstance(router.model, MockModel)

    def test_init_with_ollama(self, ollama_settings):
        """ModelRouter should create an OllamaModel when provider is ollama."""
        router = ModelRouter(ollama_settings)
        assert isinstance(router.model, OllamaModel)

    def test_init_with_openai(self, openai_settings):
        """ModelRouter should create an OpenAIModel when provider is openai."""
        router = ModelRouter(openai_settings)
        assert isinstance(router.model, OpenAIModel)

    def test_invalid_provider_raises(self):
        """Unknown provider should raise AssistantError."""
        settings = Settings(model_provider="unknown")
        with pytest.raises(AssistantError, match="Unknown provider"):
            ModelRouter(settings)

    def test_generate_with_mock(self, mock_settings):
        """ModelRouter.generate should return a ModelResponse."""
        router = ModelRouter(mock_settings)
        response = router.generate("Hello")
        assert isinstance(response, ModelResponse)
        assert response.provider == PROVIDER_MOCK

    def test_generate_with_context(self, mock_settings):
        """ModelRouter.generate should accept and pass context."""
        router = ModelRouter(mock_settings)
        context = [{"role": "user", "content": "Hi"}]
        response = router.generate("Hello again", context=context)
        assert isinstance(response, ModelResponse)

    def test_generate_empty_prompt_raises(self, mock_settings):
        """Empty prompt should raise AssistantError."""
        router = ModelRouter(mock_settings)
        with pytest.raises(AssistantError, match="cannot be empty"):
            router.generate("")
        with pytest.raises(AssistantError, match="cannot be empty"):
            router.generate("   ")

    def test_repr(self, mock_settings):
        """__repr__ should include provider and model info."""
        router = ModelRouter(mock_settings)
        r = repr(router)
        assert PROVIDER_MOCK in r
        assert "mock-v1" in r

    def test_switch_provider_via_init(self, mock_settings, ollama_settings):
        """Re-initializing ModelRouter with new settings should switch provider."""
        router = ModelRouter(mock_settings)
        assert isinstance(router.model, MockModel)

        router.__init__(ollama_settings)
        assert isinstance(router.model, OllamaModel)
        assert router.model.model_name == "llama3.2:1b"


# ============================================================
# ModelResponse Tests
# ============================================================


class TestModelResponse:
    def test_create_response(self):
        """ModelResponse should store all fields."""
        resp = ModelResponse(
            text="Hello world",
            model_name="test-model",
            provider="test",
            latency_ms=150.5,
            tokens_used=42,
            raw={"key": "value"},
        )
        assert resp.text == "Hello world"
        assert resp.model_name == "test-model"
        assert resp.provider == "test"
        assert resp.latency_ms == 150.5
        assert resp.tokens_used == 42
        assert resp.raw == {"key": "value"}

    def test_repr(self):
        """__repr__ should show truncated text."""
        resp = ModelResponse(text="Hello world", model_name="m", provider="p")
        r = repr(resp)
        assert "Hello" in r
        assert "p" in r
