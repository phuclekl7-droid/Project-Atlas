"""
Multi-LLM Parallel Routing (Feature #1).
Sends the same prompt to multiple providers simultaneously and returns a comparison.

Usage:
    router = ParallelRouter(model_router)
    result = await router.route_parallel("What is Python?", providers=["openai", "gemini", "mock"])
    print(result.comparison_table)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.model_router import ModelResponse, ModelRouter
from src.settings import Settings

logger = setup_logger("parallel_router")


@dataclass
class ParallelResult:
    """Result from a parallel multi-LLM routing call."""

    prompt: str
    responses: dict[str, ModelResponse] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    total_latency_ms: float = 0.0
    providers_requested: list[str] = field(default_factory=list)

    @property
    def successful_providers(self) -> list[str]:
        return list(self.responses.keys())

    @property
    def failed_providers(self) -> list[str]:
        return list(self.errors.keys())

    @property
    def comparison_table(self) -> str:
        """Generate a markdown comparison table of all responses."""
        lines = [
            f"## 🔄 Multi-LLM Comparison",
            f"",
            f"> **Prompt:** {self.prompt[:200]}",
            f"> **Providers tried:** {', '.join(self.providers_requested)}",
            f"> **Total time:** {self.total_latency_ms:.0f}ms",
            f"",
        ]

        for provider, resp in self.responses.items():
            preview = resp.text[:300].replace("\n", " ")
            lines.append(f"### ✅ {provider.upper()} ({resp.model_name})")
            lines.append(f"- **Latency:** {resp.latency_ms:.0f}ms")
            if resp.tokens_used:
                lines.append(f"- **Tokens:** {resp.tokens_used}")
            lines.append(f"- **Response:** {preview}...")
            lines.append("")

        for provider, err in self.errors.items():
            lines.append(f"### ❌ {provider.upper()} — Failed")
            lines.append(f"- **Error:** {err[:200]}")
            lines.append("")

        lines.append("---")
        lines.append(f"🔄 Parallel routing | {len(self.responses)} success, {len(self.errors)} failed")
        return "\n".join(lines)

    def best_response(self, prefer_fast: bool = True) -> Optional[ModelResponse]:
        """Pick the best response: fastest by default, or longest by content."""
        if not self.responses:
            return None
        if prefer_fast:
            return min(self.responses.values(), key=lambda r: r.latency_ms or float("inf"))
        return max(self.responses.values(), key=lambda r: len(r.text))


class ParallelRouter:
    """
    Sends the same prompt to multiple LLM providers simultaneously.

    Uses ModelRouter.generate_with_provider() for each provider in parallel
    via asyncio.gather().

    Usage:
        router = ParallelRouter(model_router)
        # Async:
        result = await router.route_parallel("Hello!", providers=["mock", "openai"])
        # Sync wrapper:
        result = router.route_sync("Hello!", providers=["mock", "openai"])
        print(result.comparison_table)
    """

    def __init__(self, model_router: ModelRouter):
        self._router = model_router
        self._total_routes = 0

    async def _call_single_provider(
        self,
        provider: str,
        prompt: str,
        context: Optional[list[dict]] = None,
    ) -> tuple[str, Optional[ModelResponse], Optional[str]]:
        """Call a single provider and return (provider, response_or_None, error_or_None).

        Creates a temporary model instance for the specified provider using
        ModelRouter._PROVIDER_MAP and calls async_generate() on it.
        Falls back to sync generate via asyncio.to_thread if needed.
        """
        try:
            model_class = self._router._PROVIDER_MAP.get(provider)
            if model_class is None:
                raise ValueError(f"Unknown provider: {provider}")
            # Create temp settings with the requested provider
            temp_settings = Settings(
                model_provider=provider,
                ollama_url=self._router.settings.ollama_url,
                ollama_model=self._router.settings.ollama_model,
                openai_api_key=self._router.settings.openai_api_key,
                openai_model=self._router.settings.openai_model,
                gemini_api_key=self._router.settings.gemini_api_key,
                gemini_model=self._router.settings.gemini_model,
            )
            model = model_class(temp_settings)
            response = await model.async_generate(prompt, context=context)
            return provider, response, None
        except Exception as e:
            logger.warning(f"Parallel route to {provider} failed: {e}")
            return provider, None, str(e)

    async def route_parallel(
        self,
        prompt: str,
        providers: Optional[list[str]] = None,
        context: Optional[list[dict]] = None,
    ) -> ParallelResult:
        """
        Send the same prompt to multiple providers in parallel.

        Args:
            prompt: The input text
            providers: List of provider names (e.g. ["mock", "openai", "gemini"])
                       Defaults to current provider + mock
            context: Optional conversation context

        Returns:
            ParallelResult with all responses
        """
        if providers is None:
            current = self._router.settings.model_provider
            providers = [current, "mock"]

        self._total_routes += 1
        start = time.time()

        tasks = [
            self._call_single_provider(p, prompt, context)
            for p in providers
        ]
        results = await asyncio.gather(*tasks)

        total_latency = (time.time() - start) * 1000

        responses: dict[str, ModelResponse] = {}
        errors: dict[str, str] = {}
        for provider, resp, err in results:
            if resp is not None:
                responses[provider] = resp
            else:
                errors[provider] = err or "Unknown error"

        logger.info(
            f"Parallel route completed: {len(responses)} success, "
            f"{len(errors)} failed in {total_latency:.0f}ms"
        )

        return ParallelResult(
            prompt=prompt,
            responses=responses,
            errors=errors,
            total_latency_ms=total_latency,
            providers_requested=providers,
        )

    def route_sync(
        self,
        prompt: str,
        providers: Optional[list[str]] = None,
        context: Optional[list[dict]] = None,
    ) -> ParallelResult:
        """Synchronous wrapper around route_parallel().

        Uses asyncio.run() when no event loop is running, or
        loop.run_until_complete() when called from an existing loop
        (e.g., inside Streamlit/Jupyter).
        """
        coro = self.route_parallel(prompt, providers=providers, context=context)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside a running loop (e.g. Streamlit)
                return loop.run_until_complete(
                    asyncio.ensure_future(coro)
                )
            return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists
            return asyncio.run(coro)

    def get_stats(self) -> dict:
        return {"total_routes": self._total_routes}
