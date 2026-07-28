""""
Unit tests for streaming (SSE) model calls.

Tests:
- BaseModel.generate_stream default fallback
- MockModel.generate_stream (word-by-word with asyncio.sleep)
- ModelRouter.generate_stream factory
- Error handling in streaming
- Workflow process_stream integration
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core import AssistantError, ModelConnectionError
from src.model_router import ModelResponse, ModelRouter
from src.settings import PROVIDER_MOCK, Settings


# ============================================================
# BaseModel Stream Tests
# ============================================================


class TestBaseModelStream:
    def test_generate_stream_default_fallback(self):
        """BaseModel.generate_stream should yield the full response by default."""
        from src.model_router import BaseModel, ModelResponse

        class DummyModel(BaseModel):
            def _get_model_name(self):
                return "dummy"

            def generate(self, prompt, context=None, **kwargs):
                return ModelResponse(text="Xin chào!", model_name="dummy", provider="mock")

        settings = Settings(model_provider=PROVIDER_MOCK)
        model = DummyModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream("Hello!"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) == 1
        assert "Xin chào" in tokens[0]

    def test_generate_stream_return_full_text_equivalent(self):
        """Streaming should produce the same text as async_generate."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def compare():
            full = await model.async_generate("Hello!")
            tokens = []
            async for token in model.generate_stream("Hello!"):
                tokens.append(token)
            streamed = "".join(tokens)
            # Mock appends trailing spaces to words, rstrip for comparison
            assert streamed.rstrip() == full.text.rstrip()
            return True

        assert asyncio.run(compare())


# ============================================================
# MockModel Stream Tests
# ============================================================


class TestMockModelStream:
    def test_mock_stream_yields_words(self):
        """Mock stream should yield individual words with spaces."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream("Hello!"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) > 1  # Should yield multiple words
        assert all(isinstance(t, str) for t in tokens)
        assert any(" " in t for t in tokens)  # Spaces should be at end of words

    def test_mock_stream_uses_asyncio_sleep(self):
        """Mock stream should use asyncio.sleep between words."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def measure():
            start = time.time()
            async for _ in model.generate_stream("Hello!"):
                pass
            elapsed = time.time() - start
            return elapsed

        elapsed = asyncio.run(measure())
        assert elapsed > 0.01  # Should have waited at least a bit

    def test_mock_stream_hello_response(self):
        """Mock stream should return a greeting for 'hello' input."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream("Hello!"):
                tokens.append(token)
            return "".join(tokens)

        text = asyncio.run(collect())
        assert "Xin chào" in text


# ============================================================
# ModelRouter Stream Tests
# ============================================================


class TestModelRouterStream:
    def test_router_generate_stream_mock(self):
        """ModelRouter.generate_stream should work with Mock provider."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        async def collect():
            tokens = []
            async for token in router.generate_stream("Hello!"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) > 1
        assert "Xin chào" in "".join(tokens)

    def test_router_generate_stream_empty_prompt(self):
        """Empty prompt should raise AssistantError in streaming too."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        async def test():
            with pytest.raises(AssistantError, match="cannot be empty"):
                async for _ in router.generate_stream(""):
                    pass

        asyncio.run(test())

    def test_router_generate_stream_cache_skipped(self):
        """Streaming should skip cache (no caching for partial results)."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings, cache_ttl=3600)

        async def run_twice():
            tokens1 = []
            async for t in router.generate_stream("Hello!", use_cache=True):
                tokens1.append(t)
            stats = router.get_cache_stats()
            # Cache should have no hits/misses since Mock skips cache
            assert stats["hits"] == 0
            assert stats["misses"] == 0
            return True

        assert asyncio.run(run_twice())


# ============================================================
# Stream Error Handling
# ============================================================


class TestStreamErrorHandling:
    def test_ollama_stream_connection_error(self):
        """Ollama stream should raise ModelConnectionError on connection failure."""
        from src.model_router import OllamaModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            ollama_url="http://localhost:99999",
        )
        model = OllamaModel(settings)

        async def test():
            with pytest.raises(ModelConnectionError, match="Cannot connect"):
                async for _ in model.generate_stream("Hello!"):
                    pass

        asyncio.run(test())

    def test_openai_stream_no_api_key(self):
        """OpenAI stream without API key should raise ConfigurationError."""
        from src.model_router import OpenAIModel
        from src.core import ConfigurationError
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            openai_api_key="",
        )
        model = OpenAIModel(settings)

        async def test():
            with pytest.raises(ConfigurationError, match="API key"):
                async for _ in model.generate_stream("Hello!"):
                    pass

        asyncio.run(test())


# ============================================================
# Workflow Stream Integration
# ============================================================


class TestWorkflowStreamIntegration:
    def test_workflow_process_stream_llm(self, workflow, memory):
        """Workflow.process_stream should stream tokens for LLM responses."""
        session_id = memory.create_session()

        async def collect():
            tokens = []
            async for token in workflow.process_stream(
                "Hello!",
                session_id=session_id,
            ):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) > 0
        assert any("Xin chào" in t for t in tokens)

        # Verify message saved to memory
        messages = memory.get_messages(session_id)
        assert len(messages) == 2  # user + assistant

    def test_workflow_process_stream_plugin(self, workflow, memory):
        """Workflow.process_stream should yield plugin output as single token."""
        session_id = memory.create_session()

        async def collect():
            tokens = []
            async for token in workflow.process_stream(
                "2 + 3",
                session_id=session_id,
            ):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) == 1
        assert "5" in tokens[0] or "5" in tokens  # Calculator result

        # Verify message saved to memory
        messages = memory.get_messages(session_id)
        assert len(messages) == 2

    def test_workflow_process_stream_empty_input(self, workflow, memory):
        """Empty input should raise AssistantError in stream mode."""
        session_id = memory.create_session()

        async def test():
            with pytest.raises(AssistantError, match="cannot be empty"):
                async for _ in workflow.process_stream("", session_id=session_id):
                    pass

        asyncio.run(test())

    def test_workflow_process_stream_saves_to_memory(self, workflow, memory):
        """Full streamed response should be saved to memory after streaming."""
        session_id = memory.create_session()

        async def stream():
            async for _ in workflow.process_stream("Hello!", session_id=session_id):
                pass

        asyncio.run(stream())
        messages = memory.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello!"
        assert messages[1].role == "assistant"
        assert len(messages[1].content) > 0
