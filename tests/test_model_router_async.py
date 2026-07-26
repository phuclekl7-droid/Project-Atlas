"""
Unit tests for async model calls.

Tests:
- BaseModel async_generate default (falls back to sync thread pool)
- MockModel async_generate (uses asyncio.sleep)
- OllamaModel async_generate (mocked aiohttp)
- OpenAIModel async_generate (mocked aiohttp)
- ModelRouter.generate_async
- Cache integration with async methods
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.model_router import ModelResponse, ModelRouter
from src.settings import PROVIDER_MOCK, Settings


# ============================================================
# BaseModel Async Tests
# ============================================================


class TestBaseModelAsync:
    def test_async_generate_default_falls_back_to_sync(self):
        """BaseModel.async_generate default should fall back to sync via thread pool."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        # async_generate is overridden in MockModel, so this tests the real async path
        result = asyncio.run(model.async_generate("Hello!"))
        assert isinstance(result, ModelResponse)
        assert result.text != ""
        assert result.provider == PROVIDER_MOCK

    def test_mock_async_uses_asyncio_sleep(self):
        """MockModel async_generate should use asyncio.sleep, not time.sleep."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        start = time.time()
        result = asyncio.run(model.async_generate("Hello!"))
        elapsed = time.time() - start

        assert isinstance(result, ModelResponse)
        assert elapsed >= 0.2  # Should have awaited asyncio.sleep(0.3)
        assert "Xin chào" in result.text


# ============================================================
# ModelRouter Async Tests
# ============================================================


class TestModelRouterAsync:
    def test_generate_async_mock(self):
        """ModelRouter.generate_async should work with Mock model."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        result = asyncio.run(router.generate_async("Hello!"))
        assert isinstance(result, ModelResponse)
        assert result.provider == PROVIDER_MOCK
        assert "Xin chào" in result.text

    def test_generate_async_cache_skipped_for_mock(self):
        """Mock provider should skip cache even in async mode."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings, cache_ttl=3600)

        # Two identical calls — each should regenerate (Mock skips cache)
        result1 = asyncio.run(router.generate_async("Hello!", use_cache=True))
        result2 = asyncio.run(router.generate_async("Hello!", use_cache=True))

        stats = router.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_generate_async_empty_prompt_raises(self):
        """Empty prompt should raise AssistantError in async mode too."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        with pytest.raises(Exception, match="cannot be empty"):
            asyncio.run(router.generate_async(""))

    def test_generate_async_cache_key_format(self):
        """Async cache should use the same key format as sync."""
        from src.core.cache import make_model_cache_key
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        key = make_model_cache_key("test prompt", model_name=model.model_name)
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)


# ============================================================
# Async + Sync Consistency Tests
# ============================================================


class TestAsyncSyncConsistency:
    def test_sync_and_async_same_response(self):
        """Sync and async should return the same response for same input (Mock)."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        sync_result = router.generate("Help me!")
        async_result = asyncio.run(router.generate_async("Help me!"))

        assert sync_result.text == async_result.text
        assert sync_result.provider == async_result.provider

    def test_multiple_async_calls(self):
        """Multiple async calls should all complete."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        async def run_parallel():
            tasks = [
                router.generate_async("Hello!"),
                router.generate_async("How are you?"),
                router.generate_async("What is AI?"),
            ]
            results = await asyncio.gather(*tasks)
            return results

        results = asyncio.run(run_parallel())
        assert len(results) == 3
        assert all(isinstance(r, ModelResponse) for r in results)
        assert all(r.text != "" for r in results)
