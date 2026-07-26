"""
Pytest fixtures shared across all test modules.

Provides:
- Settings fixtures for mock, ollama, and openai providers
- mock_ollama_chat_response and mock_openai_chat_response payload fixtures
- mock_ollama_error_response fixture for error scenarios
"""

import pytest

from src.settings import Settings, PROVIDER_MOCK, PROVIDER_OLLAMA, PROVIDER_OPENAI


# ── Disable logging during tests (cleaner output) ──
@pytest.fixture(autouse=True)
def _disable_logging():
    """Disable all loggers during tests to avoid clutter."""
    import logging
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


# ── Settings Fixtures ──

@pytest.fixture
def default_settings() -> Settings:
    """Return a Settings instance with all default values."""
    return Settings()


@pytest.fixture
def mock_settings() -> Settings:
    """Return a Settings instance configured for the Mock provider."""
    return Settings(model_provider=PROVIDER_MOCK)


@pytest.fixture
def ollama_settings() -> Settings:
    """Return a Settings instance configured for Ollama."""
    return Settings(
        model_provider=PROVIDER_OLLAMA,
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2:1b",
    )


@pytest.fixture
def openai_settings() -> Settings:
    """Return a Settings instance configured for OpenAI (with fake key)."""
    return Settings(
        model_provider=PROVIDER_OPENAI,
        openai_api_key="sk-test-fake-key-12345",
        openai_model="gpt-4o-mini",
    )


# ── Mock Response Fixtures ──


@pytest.fixture
def mock_ollama_chat_response() -> dict:
    """Standard successful Ollama /api/chat response payload."""
    return {
        "model": "llama3.2:1b",
        "message": {
            "role": "assistant",
            "content": "Hello! I'm your local AI assistant running on Ollama. How can I help you today?",
        },
        "done": True,
    }


@pytest.fixture
def mock_openai_chat_response() -> dict:
    """Standard successful OpenAI chat completion response payload."""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! I'm OpenAI. How can I assist you today?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 12,
            "total_tokens": 22,
        },
    }


@pytest.fixture
def mock_ollama_error_response() -> dict:
    """Ollama error response (model not found)."""
    return {"error": "model 'nonexistent' not found"    }
