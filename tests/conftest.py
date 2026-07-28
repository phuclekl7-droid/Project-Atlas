"""
Pytest fixtures shared across all test modules.

Provides:
- Settings fixtures for mock, ollama, and openai providers
- mock_ollama_chat_response and mock_openai_chat_response payload fixtures
- mock_ollama_error_response fixture for error scenarios
"""

import pytest

from src.settings import Settings, PROVIDER_MOCK, PROVIDER_OLLAMA, PROVIDER_OPENAI, PROVIDER_GEMINI


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


@pytest.fixture
def gemini_settings() -> Settings:
    """Return a Settings instance configured for Gemini (with fake key)."""
    return Settings(
        model_provider=PROVIDER_GEMINI,
        gemini_api_key="fake-gemini-key-12345",
        gemini_model="gemini-2.0-flash",
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


# ── Memory & Model Router Fixtures (shared by multiple test files) ──


@pytest.fixture
def memory(tmp_path) -> "Memory":
    """Create a temporary Memory instance."""
    from src.memory import Memory
    db_path = tmp_path / "test_shared.db"
    mem = Memory(str(db_path))
    yield mem
    mem.close()


@pytest.fixture
def model_router(mock_settings) -> "ModelRouter":
    """Create a ModelRouter with Mock provider."""
    from src.model_router import ModelRouter
    return ModelRouter(mock_settings)


@pytest.fixture
def plugin_loader() -> "PluginLoader":
    """Create a PluginLoader and discover plugins."""
    from src.plugin import PluginLoader
    loader = PluginLoader(plugin_package="src.plugins")
    loader.discover()
    return loader


@pytest.fixture
def workflow(memory, model_router, plugin_loader) -> "Workflow":
    """Create a Workflow with all dependencies."""
    from src.workflow import Workflow
    return Workflow(
        memory=memory,
        model_router=model_router,
        plugin_loader=plugin_loader,
        max_context_messages=5,
    )


@pytest.fixture
def workflow_no_plugins(memory, model_router) -> "Workflow":
    """Create a Workflow without plugins."""
    from src.workflow import Workflow
    return Workflow(
        memory=memory,
        model_router=model_router,
        plugin_loader=None,
        max_context_messages=5,
    )


# ── Token Counter Fixtures ──


@pytest.fixture
def token_counter() -> "TokenCounter":
    """Create a TokenCounter instance (uses character-based fallback if tiktoken unavailable)."""
    from src.core.token_counter import TokenCounter
    return TokenCounter()


@pytest.fixture
def token_counter_with_tiktok() -> "Optional[TokenCounter]":
    """Create a TokenCounter only if tiktoken is available. Returns None otherwise."""
    from src.core.token_counter import TokenCounter, _HAS_TIKTOKEN
    if not _HAS_TIKTOKEN:
        return None
    return TokenCounter(model_name="gpt-4o-mini")
