"""
Tests for Feature #1: Multi-LLM Parallel Routing.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.parallel_router import ParallelRouter, ParallelResult
from src.model_router import ModelResponse, ModelRouter


@pytest.fixture
def mock_model_router():
    """Create a mock ModelRouter with async provider support."""
    router = MagicMock(spec=ModelRouter)

    async def mock_async_gen(provider, prompt, context=None):
        responses = {
            "mock": ModelResponse(
                text="Mock response", model_name="mock-v1",
                provider="mock", latency_ms=100.0, tokens_used=50,
            ),
            "openai": ModelResponse(
                text="OpenAI response", model_name="gpt-4o-mini",
                provider="openai", latency_ms=200.0, tokens_used=75,
            ),
            "gemini": ModelResponse(
                text="Gemini response", model_name="gemini-2.0-flash",
                provider="gemini", latency_ms=150.0, tokens_used=60,
            ),
        }
        resp = responses.get(provider)
        if resp is None:
            raise ValueError(f"Unknown provider: {provider}")
        return resp

    router.generate_with_provider_async = AsyncMock(side_effect=mock_async_gen)
    router.settings = MagicMock()
    router.settings.model_provider = "mock"
    return router


class TestParallelResult:
    """Tests for the ParallelResult dataclass."""

    def test_empty_result(self):
        result = ParallelResult(prompt="test", providers_requested=[])
        assert result.successful_providers == []
        assert result.failed_providers == []
        assert result.best_response() is None

    def test_best_response_fastest(self):
        result = ParallelResult(prompt="test", providers_requested=["mock", "openai"])
        result.responses["mock"] = ModelResponse(
            text="fast", model_name="m1", provider="mock", latency_ms=50.0)
        result.responses["openai"] = ModelResponse(
            text="slow but detailed", model_name="o1", provider="openai", latency_ms=500.0)
        best = result.best_response(prefer_fast=True)
        assert best is not None
        assert best.provider == "mock"

    def test_best_response_longest(self):
        result = ParallelResult(prompt="test", providers_requested=["mock", "openai"])
        result.responses["mock"] = ModelResponse(
            text="short", model_name="m1", provider="mock")
        result.responses["openai"] = ModelResponse(
            text="longer detailed response", model_name="o1", provider="openai")
        best = result.best_response(prefer_fast=False)
        assert best is not None
        assert best.provider == "openai"

    def test_comparison_table(self):
        result = ParallelResult(prompt="Hello", providers_requested=["mock"])
        result.responses["mock"] = ModelResponse(
            text="Hi there!", model_name="mock-v1", provider="mock", latency_ms=100)
        table = result.comparison_table
        assert "Multi-LLM Comparison" in table
        assert "MOCK" in table
        assert "Hi there!" in table

    def test_errors_in_table(self):
        result = ParallelResult(prompt="test", providers_requested=["mock", "openai"])
        result.errors["openai"] = "API key not configured"
        result.responses["mock"] = ModelResponse(
            text="ok", model_name="m1", provider="mock")
        table = result.comparison_table
        assert "openai" in table.lower()
        assert "API key" in table


class TestParallelRouter:
    """Tests for the ParallelRouter class."""

    def test_route_parallel_basic(self, mock_model_router):
        router = ParallelRouter(mock_model_router)
        result = asyncio.run(router.route_parallel("Hello!", providers=["mock"]))
        assert "mock" in result.responses
        assert result.responses["mock"].text == "Mock response"

    def test_route_parallel_multiple(self, mock_model_router):
        router = ParallelRouter(mock_model_router)
        result = asyncio.run(
            router.route_parallel("Hi!", providers=["mock", "openai"])
        )
        assert len(result.responses) == 2
        assert "mock" in result.responses
        assert "openai" in result.responses

    def test_route_parallel_error_handling(self, mock_model_router):
        """Test that a failing provider doesn't crash the whole route."""
        router = ParallelRouter(mock_model_router)
        result = asyncio.run(
            router.route_parallel("Hi!", providers=["mock", "nonexistent"])
        )
        assert "mock" in result.responses
        assert "nonexistent" in result.errors

    def test_route_sync_wrapper(self, mock_model_router):
        router = ParallelRouter(mock_model_router)
        result = router.route_sync("Sync test", providers=["mock"])
        assert result.responses["mock"].text == "Mock response"

    def test_default_providers(self, mock_model_router):
        """When no providers specified, default to current + mock."""
        router = ParallelRouter(mock_model_router)
        result = asyncio.run(router.route_parallel("test"))
        assert "mock" in result.providers_requested

    def test_get_stats(self, mock_model_router):
        router = ParallelRouter(mock_model_router)
        assert router.get_stats()["total_routes"] == 0
        asyncio.run(router.route_parallel("test", providers=["mock"]))
        assert router.get_stats()["total_routes"] == 1


class TestEdgeCases:
    """Edge cases for parallel routing."""

    def test_empty_prompt(self, mock_model_router):
        router = ParallelRouter(mock_model_router)
        result = asyncio.run(router.route_parallel("", providers=["mock"]))
        assert "mock" in result.responses

    def test_long_prompt(self, mock_model_router):
        router = ParallelRouter(mock_model_router)
        long_prompt = "Hello " * 1000
        result = asyncio.run(router.route_parallel(long_prompt, providers=["mock"]))
        assert result.successful_providers == ["mock"]
