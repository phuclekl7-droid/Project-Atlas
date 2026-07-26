"""
Model Router module: Acts as an interface to communicate with different LLMs (Ollama, OpenAI, Gemini, etc.).
Supports plug-and-play: changing the provider in Settings is enough to switch.
Now supports conversation context injection for memory/stateful conversations.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    setup_logger,
    truncate_text,
)
from src.core.cache import SimpleTTLCache, make_model_cache_key
from src.settings import (
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_GEMINI,
    Settings,
)

logger = setup_logger("model_router")


# ============================================================
# Data Models
# ============================================================


@dataclass
class ModelResponse:
    """Standardized response from any model provider."""

    text: str
    model_name: str
    provider: str
    latency_ms: float = 0.0
    tokens_used: Optional[int] = None
    raw: Optional[Any] = None

    def __repr__(self) -> str:
        preview = truncate_text(self.text, max_length=60)
        return (
            f"ModelResponse("
            f"provider={self.provider!r}, "
            f"model={self.model_name!r}, "
            f"latency={self.latency_ms:.1f}ms, "
            f"text={preview!r})"
        )


# ============================================================
# Abstract Base Model
# ============================================================


class BaseModel(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = self._get_model_name()

    @abstractmethod
    def _get_model_name(self) -> str:
        """Return the model name/identifier for this provider."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt (with optional conversation context) to the model.

        Args:
            prompt: The new user input text
            context: Optional list of {"role": str, "content": str} dicts
                     representing conversation history (oldest first).
                     Roles are typically "user" or "assistant".
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with the model's output
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"


# ============================================================
# Mock Model (for testing without real LLM)
# ============================================================


class MockModel(BaseModel):
    """A mock model that returns canned responses for testing purposes."""

    def _get_model_name(self) -> str:
        return "mock-v1"

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        ctx_count = len(context) if context else 0
        logger.info(
            f"MockModel received prompt ({len(prompt)} chars, "
            f"context_messages={ctx_count})"
        )
        time.sleep(0.3)  # Simulate latency

        # Build a context-aware response
        has_context_prefix = "📝 **Context**" if ctx_count > 0 else ""

        # Simulate some basic "intelligence"
        prompt_lower = prompt.lower()
        if "hello" in prompt_lower or "hi" in prompt_lower or "xin chào" in prompt_lower:
            response_text = (
                "👋 Xin chào! Tôi là trợ lý AI cá nhân. "
                "Tôi đang chạy ở chế độ **Mock** để kiểm tra luồng hoạt động. "
                "Hãy cấu hình Ollama hoặc OpenAI trong file .env để có câu trả lời thực tế nhé!"
            )
        elif "who are you" in prompt_lower or "bạn là ai" in prompt_lower:
            response_text = (
                "Tôi là **Personal AI Assistant** - một trợ lý AI cá nhân tinh gọn, "
                "được thiết kế để chạy trên máy tính cá nhân. "
                "Hiện tại tôi đang ở chế độ Mock để test luồng xử lý."
            )
        elif "help" in prompt_lower or "giúp" in prompt_lower:
            response_text = (
                "Tôi có thể giúp gì cho bạn? Một số điều tôi có thể làm:\n"
                "- Trả lời câu hỏi thông qua kết nối tới các mô hình ngôn ngữ\n"
                "- Ghi nhớ ngữ cảnh hội thoại (đã hoạt động!)\n"
                "- Chạy các plugin mở rộng (sắp có)\n\n"
                f"ℹ️  Session này đã có {ctx_count} tin nhắn trong lịch sử."
            )
        else:
            response_text = (
                f"🤖 **[Mock Response]** Bạn đã nói:\n\n"
                f"  \"{truncate_text(prompt, max_length=200)}\"\n\n"
                f"ℹ️  Số tin nhắn trong context: {ctx_count}\n\n"
                f"Đây là câu trả lời mô phỏng. Để nhận phản hồi thực từ AI, "
                f"vui lòng:\n"
                f"  1. Cài đặt Ollama (https://ollama.com) và chạy 'ollama pull llama3.2:1b'\n"
                f"  2. Hoặc thiết lập API key cho OpenAI/Gemini trong file .env"
            )

        logger.info("MockModel generated response")
        return ModelResponse(
            text=response_text,
            model_name=self.model_name,
            provider=PROVIDER_MOCK,
            latency_ms=300.0,
        )


# ============================================================
# Ollama Model (Local) — uses /api/chat with message history
# ============================================================


class OllamaModel(BaseModel):
    """Connects to a local Ollama instance using the chat API."""

    def _get_model_name(self) -> str:
        return self.settings.ollama_model

    def _build_url(self, endpoint: str) -> str:
        base = self.settings.ollama_url.rstrip("/")
        return f"{base}/api/{endpoint.lstrip('/')}"

    def _build_messages(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build a messages array with context history + new user prompt."""
        messages = list(context) if context else []
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        url = self._build_url("chat")
        messages = self._build_messages(prompt, context)

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

        ctx_info = f", context_messages={len(context)}" if context else ""
        logger.info(
            f"Ollama: sending request to {url} "
            f"(model={self.model_name}, messages={len(messages)}{ctx_info})"
        )

        try:
            start = time.time()
            response = requests.post(url, json=payload, timeout=120)
            elapsed = (time.time() - start) * 1000

            if response.status_code != 200:
                raise ModelConnectionError(
                    f"Ollama returned HTTP {response.status_code}",
                    details=response.text[:500],
                )

            data = response.json()
            text = data.get("message", {}).get("content", "")

            logger.info(f"Ollama: response received in {elapsed:.0f}ms")
            return ModelResponse(
                text=text,
                model_name=self.model_name,
                provider=PROVIDER_OLLAMA,
                latency_ms=elapsed,
                tokens_used=None,
                raw=data,
            )

        except requests.ConnectionError as e:
            raise ModelConnectionError(
                f"Cannot connect to Ollama at {url}. "
                f"Is Ollama running?",
                details=str(e),
            )
        except requests.Timeout:
            raise ModelConnectionError(
                f"Ollama request timed out after 120s",
            )
        except Exception as e:
            raise ModelConnectionError(
                f"Ollama request failed unexpectedly",
                details=str(e),
            )


# ============================================================
# OpenAI Model — injects context into messages array
# ============================================================


class OpenAIModel(BaseModel):
    """Connects to OpenAI API (or any OpenAI-compatible endpoint)."""

    def _get_model_name(self) -> str:
        return self.settings.openai_model

    def _build_messages(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build a messages array with context history + new user prompt."""
        messages = list(context) if context else []
        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        api_key = self.settings.openai_api_key
        if not api_key:
            raise ConfigurationError("OpenAI API key is not configured")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = self._build_messages(prompt, context)

        payload = {
            "model": self.model_name,
            "messages": messages,
            **kwargs,
        }

        ctx_info = f", context_messages={len(context)}" if context else ""
        logger.info(
            f"OpenAI: sending request "
            f"(model={self.model_name}, messages={len(messages)}{ctx_info})"
        )

        try:
            start = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            elapsed = (time.time() - start) * 1000

            if response.status_code != 200:
                raise ModelConnectionError(
                    f"OpenAI returned HTTP {response.status_code}",
                    details=response.text[:500],
                )

            data = response.json()
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            logger.info(f"OpenAI: response received in {elapsed:.0f}ms")
            return ModelResponse(
                text=text,
                model_name=self.model_name,
                provider=PROVIDER_OPENAI,
                latency_ms=elapsed,
                tokens_used=usage.get("total_tokens"),
                raw=data,
            )

        except requests.ConnectionError as e:
            raise ModelConnectionError(
                f"Cannot connect to OpenAI API",
                details=str(e),
            )
        except requests.Timeout:
            raise ModelConnectionError(
                f"OpenAI request timed out after 60s",
            )
        except Exception as e:
            raise ModelConnectionError(
                f"OpenAI request failed unexpectedly",
                details=str(e),
            )


# ============================================================
# Model Router Factory
# ============================================================


class ModelRouter:
    """
    Routes prompts to the appropriate model provider based on settings.

    Supports conversation context via the `context` parameter
    and optional caching of model responses.

    Usage:
        router = ModelRouter(settings)
        response = router.generate("Hello!")
        response2 = router.generate("What did I say?", context=history)
    """

    _PROVIDER_MAP = {
        PROVIDER_MOCK: MockModel,
        PROVIDER_OLLAMA: OllamaModel,
        PROVIDER_OPENAI: OpenAIModel,
    }

    def __init__(
        self,
        settings: Settings,
        cache_ttl: int = 3600,  # 1 hour default
        cache_max_size: int = 100,
    ):
        self.settings = settings
        self.model = self._create_model()
        self._cache = SimpleTTLCache(
            max_size=cache_max_size,
            ttl_seconds=cache_ttl,
        )
        logger.info(
            f"ModelRouter initialized: "
            f"provider={settings.model_provider}, "
            f"model={self.model.model_name}, "
            f"cache_ttl={cache_ttl}s"
        )

    def _create_model(self) -> BaseModel:
        provider = self.settings.model_provider
        model_class = self._PROVIDER_MAP.get(provider)

        if model_class is None:
            raise AssistantError(
                f"Unknown provider '{provider}'. "
                f"Supported: {', '.join(sorted(self._PROVIDER_MAP.keys()))}"
            )

        return model_class(self.settings)

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt to the configured model and return the response.

        Args:
            prompt: The input text
            context: Optional list of {"role": str, "content": str} dicts
            use_cache: Whether to check and store in response cache
            **kwargs: Additional parameters passed to the underlying model

        Returns:
            ModelResponse with the generated text
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        # Check cache first (skip for Mock to always get fresh responses)
        if use_cache and self.settings.model_provider != PROVIDER_MOCK:
            cache_key = make_model_cache_key(prompt, context, self.model.model_name)
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Model response cache HIT")
                return cached

        # Cache miss — call the actual model
        ctx_info = f", context={len(context)} messages" if context else ""
        logger.debug(f"Routing prompt ({len(prompt)} chars{ctx_info}) to {self.model}")
        response = self.model.generate(prompt, context=context, **kwargs)

        # Store in cache (skip Mock)
        if use_cache and self.settings.model_provider != PROVIDER_MOCK:
            cache_key = make_model_cache_key(prompt, context, self.model.model_name)
            self._cache.set(cache_key, response)

        return response

    def clear_cache(self) -> int:
        """Clear the model response cache. Returns number of entries cleared."""
        return self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Get model cache statistics."""
        return self._cache.get_stats()

    def __repr__(self) -> str:
        return f"ModelRouter(provider={self.settings.model_provider}, model={self.model})"
