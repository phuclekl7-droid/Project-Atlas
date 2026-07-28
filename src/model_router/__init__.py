"""
Model Router module: Acts as an interface to communicate with different LLMs (Ollama, OpenAI, Gemini, etc.).
Supports plug-and-play: changing the provider in Settings is enough to switch.
Now supports conversation context injection for memory/stateful conversations.

Async support:
- BaseModel.async_generate() for non-blocking API calls
- Uses aiohttp instead of requests for async operations
- MockModel uses asyncio.sleep instead of time.sleep
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

import aiohttp
import requests

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    setup_logger,
    truncate_text,
)
from src.core.cache import SimpleTTLCache, make_model_cache_key
from src.core.rate_limiter import RateLimiter
from src.core.token_counter import TokenCounter
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
        Send a prompt (with optional conversation context) to the model (sync).

        Args:
            prompt: The new user input text
            context: Optional list of {"role": str, "content": str} dicts
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with the model's output
        """
        ...

    async def async_generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt to the model asynchronously (non-blocking).

        Default implementation calls sync generate in a thread pool.
        Override in subclasses for true async (aiohttp).

        Args:
            prompt: The new user input text
            context: Optional conversation history
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with the model's output
        """
        return await asyncio.to_thread(
            self.generate, prompt, context=context, **kwargs
        )

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from the model asynchronously.

        Default implementation yields the full response as a single token.
        Override in subclasses for true token-by-token streaming (SSE).

        Args:
            prompt: The input text
            context: Optional conversation history
            **kwargs: Additional provider-specific parameters

        Yields:
            str: Individual response tokens
        """
        response = await self.async_generate(prompt, context=context, **kwargs)
        yield response.text

    def check_health(self) -> dict:
        """
        Check if this provider is reachable and authenticated.

        Returns a dict with keys:
            - provider: str (e.g. 'mock', 'ollama')
            - ok: bool
            - latency_ms: float
            - error: Optional[str] (None if ok)
            - model: str
        """
        return {
            "provider": "base",
            "ok": False,
            "latency_ms": 0.0,
            "error": "Not implemented",
            "model": self.model_name,
        }

    def generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt with an image to the model (vision support).

        Default implementation falls back to text-only generate.
        Override in subclasses for true vision model support.

        Args:
            prompt: The text prompt describing the image
            image_base64: Base64-encoded image data URI
            context: Optional conversation history
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with the model's analysis of the image
        """
        logger.debug(f"{self.__class__.__name__}: vision not supported, falling back to text")
        return self.generate(
            f"[Image analysis requested] {prompt}",
            context=context,
            **kwargs,
        )

    async def async_generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt with an image to the model asynchronously (vision support).

        Default implementation falls back to text-only async_generate.
        Override in subclasses for true async vision model support.

        Args:
            prompt: The text prompt describing the image
            image_base64: Base64-encoded image data URI
            context: Optional conversation history
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with the model's analysis of the image
        """
        return await asyncio.to_thread(
            self.generate_with_image, prompt, image_base64, context=context, **kwargs
        )

    async def generate_stream_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from a vision model asynchronously (token-by-token).

        Default implementation falls back to streaming the full vision response
        as one token. Override in subclasses for true token-by-token
        streaming from vision models (e.g. GPT-4o, Gemini Pro Vision, LLaVA).

        Args:
            prompt: The text prompt describing the image
            image_base64: Base64-encoded image data URI
            context: Optional conversation history
            **kwargs: Additional provider-specific parameters

        Yields:
            str: Individual response tokens from the vision model
        """
        logger.debug(
            f"{self.__class__.__name__}: vision streaming not natively supported, "
            f"falling back to single-shot async vision"
        )
        response = await self.async_generate_with_image(
            prompt, image_base64, context=context, **kwargs
        )
        yield response.text

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"


# ============================================================
# Mock Model (for testing without real LLM)
# ============================================================


class MockModel(BaseModel):
    """A mock model that returns canned responses for testing purposes."""

    def _get_model_name(self) -> str:
        return "mock-v1"

    def _build_response(self, prompt: str, context: Optional[list[dict]] = None) -> ModelResponse:
        """Build a mock response based on the prompt content."""
        ctx_count = len(context) if context else 0
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
                "- Chạy các plugin mở rộng\n\n"
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

        return ModelResponse(
            text=response_text,
            model_name=self.model_name,
            provider=PROVIDER_MOCK,
            latency_ms=300.0,
        )

    def generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Mock vision response — returns a canned analysis."""
        ctx_count = len(context) if context else 0
        logger.info(f"MockModel: vision request ({len(prompt)} chars, context_messages={ctx_count})")
        time.sleep(0.3)

        response_text = (
            f"👁️ **[Mock Vision Response]**\n\n"
            f"Bạn đã gửi một hình ảnh kèm mô tả:\n"
            f"> {truncate_text(prompt, max_length=200) if prompt else 'không có mô tả'}\n\n"
            f"📸 **Phân tích hình ảnh (mô phỏng):**\n"
            f"- Đây là chế độ Mock — không có model vision thật\n"
            f"- Để nhận phân tích hình ảnh thực, vui lòng:\n"
            f"  1. Dùng OpenAI (GPT-4o) với API key\n"
            f"  2. Dùng Gemini với API key\n"
            f"  3. Dùng Ollama với model vision (llava, bakllava)\n\n"
            f"ℹ️  Context: {ctx_count} tin nhắn trước đó"
        )

        return ModelResponse(
            text=response_text,
            model_name=self.model_name,
            provider=PROVIDER_MOCK,
            latency_ms=300.0,
        )

    def check_health(self) -> dict:
        """Mock is always healthy — no API needed."""
        return {
            "provider": PROVIDER_MOCK,
            "ok": True,
            "latency_ms": 0.0,
            "error": None,
            "model": self.model_name,
        }

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
        logger.info("MockModel generated response")
        return self._build_response(prompt, context)

    async def async_generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        ctx_count = len(context) if context else 0
        logger.info(
            f"MockModel async received prompt ({len(prompt)} chars, "
            f"context_messages={ctx_count})"
        )
        await asyncio.sleep(0.3)  # Non-blocking delay
        logger.info("MockModel async generated response")
        return self._build_response(prompt, context)

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream Mock response token by token to simulate real-time streaming."""
        full_text = self._build_response(prompt, context).text
        words = full_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.05)  # Small delay between words for visual effect

    async def generate_stream_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream Mock vision response token by token.

        Generates a canned vision analysis and streams it word-by-word
        with short delays to simulate real-time token generation.
        """
        ctx_count = len(context) if context else 0
        response_text = (
            f"👁️ **[Mock Vision Streaming]**\n\n"
            f"Bạn đã gửi một hình ảnh kèm mô tả:\n"
            f"> {truncate_text(prompt, max_length=200) if prompt else 'không có mô tả'}\n\n"
            f"📸 **Phân tích (đang stream...)**\n"
            f"Hình ảnh này có vẻ như chứa... xin chờ một lát...\n\n"
            f"Tôi thấy có nhiều chi tiết thú vị trong ảnh. "
            f"Với Mock Mode, tôi không thể phân tích ảnh thực, "
            f"nhưng đây là mô phỏng quá trình vision streaming.\n\n"
            f"ℹ️  Context: {ctx_count} tin nhắn trước đó"
        )
        words = response_text.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            await asyncio.sleep(0.04)  # Slightly faster than text streaming


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

    def _build_payload(self, prompt: str, context: Optional[list[dict]] = None, **kwargs) -> dict:
        messages = self._build_messages(prompt, context)
        return {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            **kwargs,
        }

    def _parse_response(self, data: dict, elapsed: float) -> ModelResponse:
        text = data.get("message", {}).get("content", "")
        return ModelResponse(
            text=text,
            model_name=self.model_name,
            provider=PROVIDER_OLLAMA,
            latency_ms=elapsed,
            tokens_used=None,
            raw=data,
        )

    def generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt with an image to a vision-capable Ollama model (e.g. llava, bakllava).

        Ollama vision API expects images as a base64 array in the message object:
        {"role": "user", "content": "describe this", "images": ["base64..."]}
        Strips the "data:image/...;base64," prefix if present.
        """
        url = self._build_url("chat")
        messages = self._build_vision_messages(prompt, image_base64, context)
        payload = {"model": self.model_name, "messages": messages, "stream": False, **kwargs}
        logger.info(f"Ollama: vision request (model={self.model_name})")

        try:
            start = time.time()
            response = requests.post(url, json=payload, timeout=120)
            elapsed = (time.time() - start) * 1000
            if response.status_code != 200:
                raise ModelConnectionError(f"Ollama returned HTTP {response.status_code}", details=response.text[:500])
            data = response.json()
            logger.info(f"Ollama: vision response in {elapsed:.0f}ms")
            return self._parse_response(data, elapsed)
        except requests.ConnectionError as e:
            raise ModelConnectionError(f"Cannot connect to Ollama at {url}", details=str(e))
        except requests.Timeout:
            raise ModelConnectionError("Ollama vision request timed out")
        except Exception as e:
            raise ModelConnectionError("Ollama vision request failed", details=str(e))

    def check_health(self) -> dict:
        """Check if Ollama is running by pinging GET /api/tags."""
        url = self._build_url("tags")
        try:
            start = time.time()
            response = requests.get(url, timeout=5)
            elapsed = (time.time() - start) * 1000
            if response.status_code == 200:
                return {
                    "provider": PROVIDER_OLLAMA,
                    "ok": True,
                    "latency_ms": round(elapsed, 1),
                    "error": None,
                    "model": self.model_name,
                }
            return {
                "provider": PROVIDER_OLLAMA,
                "ok": False,
                "latency_ms": round(elapsed, 1),
                "error": f"HTTP {response.status_code}",
                "model": self.model_name,
            }
        except requests.ConnectionError:
            return {
                "provider": PROVIDER_OLLAMA,
                "ok": False,
                "latency_ms": 0.0,
                "error": "Cannot connect — is Ollama running?",
                "model": self.model_name,
            }
        except requests.Timeout:
            return {
                "provider": PROVIDER_OLLAMA,
                "ok": False,
                "latency_ms": 0.0,
                "error": "Connection timed out after 5s",
                "model": self.model_name,
            }
        except Exception as e:
            return {
                "provider": PROVIDER_OLLAMA,
                "ok": False,
                "latency_ms": 0.0,
                "error": str(e)[:100],
                "model": self.model_name,
            }

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        url = self._build_url("chat")
        payload = self._build_payload(prompt, context, **kwargs)

        ctx_info = f", context_messages={len(context)}" if context else ""
        logger.info(
            f"Ollama: sending request to {url} "
            f"(model={self.model_name}, messages={len(payload['messages'])}{ctx_info})"
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
            logger.info(f"Ollama: response received in {elapsed:.0f}ms")
            return self._parse_response(data, elapsed)

        except requests.ConnectionError as e:
            raise ModelConnectionError(
                f"Cannot connect to Ollama at {url}. Is Ollama running?",
                details=str(e),
            )
        except requests.Timeout:
            raise ModelConnectionError("Ollama request timed out after 120s")
        except Exception as e:
            raise ModelConnectionError(
                "Ollama request failed unexpectedly",
                details=str(e),
            )

    async def async_generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        url = self._build_url("chat")
        payload = self._build_payload(prompt, context, **kwargs)

        ctx_info = f", context_messages={len(context)}" if context else ""
        logger.info(
            f"Ollama: async request to {url} "
            f"(model={self.model_name}, messages={len(payload['messages'])}{ctx_info})"
        )

        try:
            async with aiohttp.ClientSession() as session:
                start = time.time()
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as response:
                    elapsed = (time.time() - start) * 1000

                    if response.status != 200:
                        text = await response.text()
                        raise ModelConnectionError(
                            f"Ollama returned HTTP {response.status}",
                            details=text[:500],
                        )

                    data = await response.json()
                    logger.info(f"Ollama: async response received in {elapsed:.0f}ms")
                    return self._parse_response(data, elapsed)

        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError(
                f"Cannot connect to Ollama at {url}. Is Ollama running?",
                details=str(e),
            )
        except asyncio.TimeoutError:
            raise ModelConnectionError("Ollama async request timed out after 120s")
        except Exception as e:
            raise ModelConnectionError(
                "Ollama async request failed unexpectedly",
                details=str(e),
            )

    def _build_stream_payload(self, prompt: str, context: Optional[list[dict]] = None, **kwargs) -> dict:
        """Build a streaming payload."""
        messages = self._build_messages(prompt, context)
        return {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            **kwargs,
        }

    def _build_vision_messages(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Build messages array with an image for vision-capable Ollama models."""
        raw_b64 = image_base64
        if "," in image_base64:
            raw_b64 = image_base64.split(",", 1)[1]
        messages = list(context) if context else []
        messages.append({
            "role": "user",
            "content": prompt,
            "images": [raw_b64],
        })
        return messages

    async def _stream_sse(self, url: str, payload: dict) -> AsyncIterator[str]:
        """Shared SSE stream parser for Ollama API."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=300)
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise ModelConnectionError(
                        f"Ollama returned HTTP {response.status}",
                        details=text[:500],
                    )

                buffer = ""
                async for chunk_bytes in response.content:
                    buffer += chunk_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            done = data.get("done", False)
                            if token:
                                yield token
                            if done:
                                return
                        except json.JSONDecodeError:
                            continue

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream Ollama response token by token via SSE."""
        url = self._build_url("chat")
        payload = self._build_stream_payload(prompt, context, **kwargs)

        logger.info(f"Ollama: streaming request to {url} (model={self.model_name})")

        try:
            async for token in self._stream_sse(url, payload):
                yield token
        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError(
                f"Cannot connect to Ollama at {url}. Is Ollama running?",
                details=str(e),
            )
        except asyncio.TimeoutError:
            raise ModelConnectionError("Ollama stream request timed out after 300s")
        except Exception as e:
            raise ModelConnectionError(
                "Ollama stream request failed unexpectedly",
                details=str(e),
            )

    async def generate_stream_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream Ollama vision model response token by token via SSE.

        For vision-capable Ollama models (e.g. llava, bakllava, moondream),
        sends the image as a base64 array in the messages and streams tokens.

        Uses the same SSE streaming engine as generate_stream() but with
        an images array in the user message payload.
        """
        url = self._build_url("chat")
        messages = self._build_vision_messages(prompt, image_base64, context)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            **kwargs,
        }

        logger.info(f"Ollama: vision streaming request (model={self.model_name})")

        try:
            async for token in self._stream_sse(url, payload):
                yield token
        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError(
                f"Cannot connect to Ollama at {url}. Is Ollama running?",
                details=str(e),
            )
        except asyncio.TimeoutError:
            raise ModelConnectionError("Ollama vision stream request timed out after 300s")
        except Exception as e:
            raise ModelConnectionError(
                "Ollama vision stream request failed unexpectedly",
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

    def _build_headers(self) -> dict:
        api_key = self.settings.openai_api_key
        if not api_key:
            raise ConfigurationError("OpenAI API key is not configured")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, prompt: str, context: Optional[list[dict]] = None, **kwargs) -> dict:
        messages = self._build_messages(prompt, context)
        return {
            "model": self.model_name,
            "messages": messages,
            **kwargs,
        }

    def _parse_response(self, data: dict, elapsed: float) -> ModelResponse:
        choice = data.get("choices", [{}])[0]
        text = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return ModelResponse(
            text=text,
            model_name=self.model_name,
            provider=PROVIDER_OPENAI,
            latency_ms=elapsed,
            tokens_used=usage.get("total_tokens"),
            raw=data,
        )

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        url = "https://api.openai.com/v1/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(prompt, context, **kwargs)

        ctx_info = f", context_messages={len(context)}" if context else ""
        logger.info(
            f"OpenAI: sending request "
            f"(model={self.model_name}, messages={len(payload['messages'])}{ctx_info})"
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
            logger.info(f"OpenAI: response received in {elapsed:.0f}ms")
            return self._parse_response(data, elapsed)

        except requests.ConnectionError as e:
            raise ModelConnectionError("Cannot connect to OpenAI API", details=str(e))
        except requests.Timeout:
            raise ModelConnectionError("OpenAI request timed out after 60s")
        except Exception as e:
            raise ModelConnectionError(
                "OpenAI request failed unexpectedly",
                details=str(e),
            )

    def _build_vision_messages(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Build messages array with an image for vision-capable models.

        Uses OpenAI's content array format:
        [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "data:base64,..."}}]

        Context messages (text-only) are included before the image message.
        """
        messages = list(context) if context else []
        # Build content array: text + image
        content_parts = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_base64, "detail": "auto"},
            },
        ]
        messages.append({"role": "user", "content": content_parts})
        return messages

    def generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt with an image to GPT-4o vision model.

        Uses OpenAI's native vision API with content array format.
        """
        url = "https://api.openai.com/v1/chat/completions"
        headers = self._build_headers()
        messages = self._build_vision_messages(prompt, image_base64, context)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 4096,
            **kwargs,
        }

        logger.info(f"OpenAI: vision request (model={self.model_name})")
        try:
            start = time.time()
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            elapsed = (time.time() - start) * 1000
            if response.status_code != 200:
                raise ModelConnectionError(
                    f"OpenAI returned HTTP {response.status_code}",
                    details=response.text[:500],
                )
            data = response.json()
            logger.info(f"OpenAI: vision response received in {elapsed:.0f}ms")
            return self._parse_response(data, elapsed)
        except requests.ConnectionError as e:
            raise ModelConnectionError("Cannot connect to OpenAI API", details=str(e))
        except requests.Timeout:
            raise ModelConnectionError("OpenAI vision request timed out after 120s")
        except Exception as e:
            raise ModelConnectionError("OpenAI vision request failed", details=str(e))

    async def async_generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Async vision request to OpenAI."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = self._build_headers()
        messages = self._build_vision_messages(prompt, image_base64, context)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 4096,
            **kwargs,
        }

        logger.info(f"OpenAI: async vision request (model={self.model_name})")
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                start = time.time()
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    elapsed = (time.time() - start) * 1000
                    if resp.status != 200:
                        text = await resp.text()
                        raise ModelConnectionError(f"OpenAI returned HTTP {resp.status}", details=text[:500])
                    data = await resp.json()
                    logger.info(f"OpenAI: async vision response in {elapsed:.0f}ms")
                    return self._parse_response(data, elapsed)
        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError("Cannot connect to OpenAI API", details=str(e))
        except asyncio.TimeoutError:
            raise ModelConnectionError("OpenAI async vision request timed out")
        except Exception as e:
            raise ModelConnectionError("OpenAI async vision request failed", details=str(e))

    def check_health(self) -> dict:
        """Check OpenAI API connectivity by sending a minimal HEAD request."""
        url = "https://api.openai.com/v1/models"
        try:
            api_key = self.settings.openai_api_key
            if not api_key:
                return {
                    "provider": PROVIDER_OPENAI,
                    "ok": False,
                    "latency_ms": 0.0,
                    "error": "API key not configured",
                    "model": self.model_name,
                }
            headers = {"Authorization": f"Bearer {api_key}"}
            start = time.time()
            response = requests.get(url, headers=headers, timeout=10)
            elapsed = (time.time() - start) * 1000
            if response.status_code == 200:
                return {
                    "provider": PROVIDER_OPENAI,
                    "ok": True,
                    "latency_ms": round(elapsed, 1),
                    "error": None,
                    "model": self.model_name,
                }
            return {
                "provider": PROVIDER_OPENAI,
                "ok": False,
                "latency_ms": round(elapsed, 1),
                "error": f"HTTP {response.status_code}",
                "model": self.model_name,
            }
        except requests.ConnectionError:
            return {
                "provider": PROVIDER_OPENAI,
                "ok": False,
                "latency_ms": 0.0,
                "error": "Cannot connect to api.openai.com",
                "model": self.model_name,
            }
        except requests.Timeout:
            return {
                "provider": PROVIDER_OPENAI,
                "ok": False,
                "latency_ms": 0.0,
                "error": "Connection timed out after 10s",
                "model": self.model_name,
            }
        except Exception as e:
            return {
                "provider": PROVIDER_OPENAI,
                "ok": False,
                "latency_ms": 0.0,
                "error": str(e)[:100],
                "model": self.model_name,
            }

    async def async_generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        url = "https://api.openai.com/v1/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(prompt, context, **kwargs)

        ctx_info = f", context_messages={len(context)}" if context else ""
        logger.info(
            f"OpenAI: async request "
            f"(model={self.model_name}, messages={len(payload['messages'])}{ctx_info})"
        )

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                start = time.time()
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    elapsed = (time.time() - start) * 1000

                    if response.status != 200:
                        text = await response.text()
                        raise ModelConnectionError(
                            f"OpenAI returned HTTP {response.status}",
                            details=text[:500],
                        )

                    data = await response.json()
                    logger.info(f"OpenAI: async response received in {elapsed:.0f}ms")
                    return self._parse_response(data, elapsed)

        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError("Cannot connect to OpenAI API", details=str(e))
        except asyncio.TimeoutError:
            raise ModelConnectionError("OpenAI async request timed out after 60s")
        except Exception as e:
            raise ModelConnectionError(
                "OpenAI async request failed unexpectedly",
                details=str(e),
            )

    async def _stream_openai_sse(self, url: str, headers: dict, payload: dict) -> AsyncIterator[str]:
        """Shared OpenAI SSE stream parser."""
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise ModelConnectionError(
                        f"OpenAI returned HTTP {response.status}",
                        details=text[:500],
                    )

                buffer = ""
                async for chunk_bytes in response.content:
                    buffer += chunk_bytes.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                return
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    token = delta.get("content", "")
                                    if token:
                                        yield token
                            except json.JSONDecodeError:
                                continue

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream OpenAI response token by token via SSE."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = self._build_headers()
        payload = self._build_payload(prompt, context, stream=True, **kwargs)

        logger.info(f"OpenAI: streaming request (model={self.model_name})")

        try:
            async for token in self._stream_openai_sse(url, headers, payload):
                yield token
        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError("Cannot connect to OpenAI API", details=str(e))
        except asyncio.TimeoutError:
            raise ModelConnectionError("OpenAI stream request timed out after 120s")
        except Exception as e:
            raise ModelConnectionError(
                "OpenAI stream request failed unexpectedly",
                details=str(e),
            )

    async def generate_stream_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream OpenAI vision model response token by token via SSE.

        Uses GPT-4o (or any vision-capable model) with the content array
        format: [{"type": "text", ...}, {"type": "image_url", ...}].
        Streams tokens in real-time as the model processes the image.
        """
        url = "https://api.openai.com/v1/chat/completions"
        headers = self._build_headers()
        messages = self._build_vision_messages(prompt, image_base64, context)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": 4096,
            "stream": True,
            **kwargs,
        }

        logger.info(f"OpenAI: vision streaming request (model={self.model_name})")

        try:
            async for token in self._stream_openai_sse(url, headers, payload):
                yield token
        except aiohttp.ClientConnectorError as e:
            raise ModelConnectionError("Cannot connect to OpenAI API", details=str(e))
        except asyncio.TimeoutError:
            raise ModelConnectionError("OpenAI vision stream request timed out after 120s")
        except Exception as e:
            raise ModelConnectionError(
                "OpenAI vision stream request failed unexpectedly",
                details=str(e),
            )


# ============================================================
# Gemini Model — uses google-generativeai library
# ============================================================


class GeminiModel(BaseModel):
    """Connects to Google Gemini API using the google-generativeai library."""

    def check_health(self) -> dict:
        """Check Gemini API health by configuring and listing models."""
        api_key = self.settings.gemini_api_key
        if not api_key:
            return {
                "provider": PROVIDER_GEMINI,
                "ok": False,
                "latency_ms": 0.0,
                "error": "API key not configured",
                "model": self.model_name,
            }
        try:
            genai = self._get_genai()
            start = time.time()
            genai.configure(api_key=api_key)
            # List models as a quick connectivity check
            _ = genai.list_models()
            elapsed = (time.time() - start) * 1000
            return {
                "provider": PROVIDER_GEMINI,
                "ok": True,
                "latency_ms": round(elapsed, 1),
                "error": None,
                "model": self.model_name,
            }
        except ConfigurationError:
            return {
                "provider": PROVIDER_GEMINI,
                "ok": False,
                "latency_ms": 0.0,
                "error": "google-generativeai not installed",
                "model": self.model_name,
            }
        except Exception as e:
            err_msg = str(e)[:100]
            if "API_KEY_INVALID" in err_msg or "API key" in err_msg:
                return {
                    "provider": PROVIDER_GEMINI,
                    "ok": False,
                    "latency_ms": 0.0,
                    "error": "API key invalid",
                    "model": self.model_name,
                }
            return {
                "provider": PROVIDER_GEMINI,
                "ok": False,
                "latency_ms": 0.0,
                "error": err_msg,
                "model": self.model_name,
            }

    def _get_genai(self):
        """
        Get the google.generativeai module (lazy import, stored on instance).

        Uses instance-level storage so each test can inject its own mock
        via `model._genai = mock_genai` without contaminating the class.
        """
        if getattr(self, "_genai", None) is not None:
            return self._genai
        try:
            import google.generativeai as genai
            self._genai = genai  # Store on INSTANCE, not class
            return genai
        except ImportError:
            raise ConfigurationError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            )

    def _get_model_name(self) -> str:
        return self.settings.gemini_model

    def _configure_api(self):
        """Configure the Gemini API with the API key."""
        api_key = self.settings.gemini_api_key
        if not api_key:
            raise ConfigurationError("Gemini API key is not configured")
        genai = self._get_genai()
        genai.configure(api_key=api_key)

    def _convert_context(
        self, context: Optional[list[dict]] = None
    ) -> Optional[list[dict]]:
        """
        Convert OpenAI-format context to Gemini history format.

        OpenAI: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        Gemini: [{"role": "user", "parts": [{"text": "..."}]}, {"role": "model", "parts": [{"text": "..."}]}]
        """
        if not context:
            return None

        history = []
        for msg in context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Gemini uses "model" instead of "assistant"
            gemini_role = "model" if role == "assistant" else "user"
            history.append({
                "role": gemini_role,
                "parts": [{"text": content}],
            })
        return history

    def generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt with an image to Gemini vision model.

        Gemini native vision: passes the base64 image as a Part in the content.
        Uses the inline_data format: {"mime_type": "...", "data": "base64..."}
        """
        self._configure_api()
        genai = self._get_genai()
        model = genai.GenerativeModel(self.model_name)

        # Parse base64 data URI: "data:image/jpeg;base64,/9j4..."
        mime_type = "image/png"
        raw_b64 = image_base64
        if "," in image_base64:
            header, raw_b64 = image_base64.split(",", 1)
            if ";" in header:
                mime_type = header.split(":", 1)[1].split(";", 1)[0]

        logger.info(f"Gemini: vision request (model={self.model_name})")

        try:
            start = time.time()

            if context:
                history = self._convert_context(context)
                chat = model.start_chat(history=history)
                response = chat.send_message(
                    [prompt, {"mime_type": mime_type, "data": raw_b64}],
                    **kwargs,
                )
            else:
                response = model.generate_content(
                    [prompt, {"mime_type": mime_type, "data": raw_b64}],
                    **kwargs,
                )

            elapsed = (time.time() - start) * 1000

            if not response.candidates:
                raise ModelConnectionError(
                    "Gemini returned empty response",
                    details=str(response.prompt_feedback) if hasattr(response, 'prompt_feedback') else None,
                )

            text = response.text
            usage = getattr(response, "usage_metadata", None)
            total_tokens = None
            if usage:
                total_tokens = usage.total_token_count if hasattr(usage, "total_token_count") else None

            logger.info(f"Gemini: vision response received in {elapsed:.0f}ms")
            return ModelResponse(
                text=text,
                model_name=self.model_name,
                provider=PROVIDER_GEMINI,
                latency_ms=elapsed,
                tokens_used=total_tokens,
                raw=response,
            )

        except ModelConnectionError:
            raise
        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "API key" in err_msg:
                raise ConfigurationError("Gemini API key is invalid")
            raise ModelConnectionError("Gemini vision request failed", details=err_msg)

    def generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        self._configure_api()
        genai = self._get_genai()
        model = genai.GenerativeModel(self.model_name)

        logger.info(f"Gemini: sending request (model={self.model_name})")

        try:
            start = time.time()

            if context:
                # Chat mode with history
                history = self._convert_context(context)
                chat = model.start_chat(history=history)
                response = chat.send_message(prompt, **kwargs)
            else:
                # Simple prompt
                response = model.generate_content(prompt, **kwargs)

            elapsed = (time.time() - start) * 1000

            if not response.candidates:
                raise ModelConnectionError(
                    "Gemini returned empty response",
                    details=str(response.prompt_feedback) if hasattr(response, 'prompt_feedback') else None,
                )

            text = response.text
            usage = getattr(response, "usage_metadata", None)
            total_tokens = None
            if usage:
                total_tokens = usage.total_token_count if hasattr(usage, "total_token_count") else None

            logger.info(f"Gemini: response received in {elapsed:.0f}ms")
            return ModelResponse(
                text=text,
                model_name=self.model_name,
                provider=PROVIDER_GEMINI,
                latency_ms=elapsed,
                tokens_used=total_tokens,
                raw=response,
            )

        except ModelConnectionError:
            raise
        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "API key" in err_msg:
                raise ConfigurationError(
                    "Gemini API key is invalid. Check your GEMINI_API_KEY in .env"
                )
            raise ModelConnectionError(
                "Gemini request failed",
                details=err_msg,
            )

    async def async_generate(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        self._configure_api()
        genai = self._get_genai()
        model = genai.GenerativeModel(self.model_name)

        logger.info(f"Gemini: async request (model={self.model_name})")

        try:
            start = time.time()

            if context:
                history = self._convert_context(context)
                chat = model.start_chat(history=history)
                response = await chat.send_message_async(prompt, **kwargs)
            else:
                response = await model.generate_content_async(prompt, **kwargs)

            elapsed = (time.time() - start) * 1000

            if not response.candidates:
                raise ModelConnectionError(
                    "Gemini returned empty response",
                    details=str(response.prompt_feedback) if hasattr(response, 'prompt_feedback') else None,
                )

            text = response.text
            usage = getattr(response, "usage_metadata", None)
            total_tokens = None
            if usage:
                total_tokens = usage.total_token_count if hasattr(usage, "total_token_count") else None

            logger.info(f"Gemini: async response received in {elapsed:.0f}ms")
            return ModelResponse(
                text=text,
                model_name=self.model_name,
                provider=PROVIDER_GEMINI,
                latency_ms=elapsed,
                tokens_used=total_tokens,
                raw=response,
            )

        except ModelConnectionError:
            raise
        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "API key" in err_msg:
                raise ConfigurationError(
                    "Gemini API key is invalid. Check your GEMINI_API_KEY in .env"
                )
            raise ModelConnectionError(
                "Gemini async request failed",
                details=err_msg,
            )

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream Gemini response token by token."""
        self._configure_api()
        genai = self._get_genai()
        model = genai.GenerativeModel(self.model_name)

        logger.info(f"Gemini: streaming request (model={self.model_name})")

        try:
            if context:
                history = self._convert_context(context)
                chat = model.start_chat(history=history)
                response = chat.send_message(prompt, stream=True, **kwargs)
            else:
                response = model.generate_content(prompt, stream=True, **kwargs)

            for chunk in response:
                    try:
                        if chunk.text:
                            yield chunk.text
                    except Exception:
                        # Gracefully skip malformed chunks
                        continue

        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "API key" in err_msg:
                raise ConfigurationError(
                    "Gemini API key is invalid. Check your GEMINI_API_KEY in .env"
                )
            raise ModelConnectionError(
                "Gemini stream request failed",
                details=err_msg,
            )

    async def generate_stream_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream Gemini vision model response token by token.

        Gemini natively supports streaming with images via
        generate_content(..., stream=True) with Parts array.

        The base64 image is passed as inline_data in the content parts.
        """
        self._configure_api()
        genai = self._get_genai()
        model = genai.GenerativeModel(self.model_name)

        # Parse base64 data URI: "data:image/jpeg;base64,/9j4..."
        mime_type = "image/png"
        raw_b64 = image_base64
        if "," in image_base64:
            header, raw_b64 = image_base64.split(",", 1)
            if ";" in header:
                mime_type = header.split(":", 1)[1].split(";", 1)[0]

        logger.info(f"Gemini: vision streaming request (model={self.model_name})")

        try:
            if context:
                history = self._convert_context(context)
                chat = model.start_chat(history=history)
                response = chat.send_message(
                    [prompt, {"mime_type": mime_type, "data": raw_b64}],
                    stream=True,
                    **kwargs,
                )
            else:
                response = model.generate_content(
                    [prompt, {"mime_type": mime_type, "data": raw_b64}],
                    stream=True,
                    **kwargs,
                )

            for chunk in response:
                try:
                    if chunk.text:
                        yield chunk.text
                except Exception:
                    continue

        except Exception as e:
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "API key" in err_msg:
                raise ConfigurationError(
                    "Gemini API key is invalid. Check your GEMINI_API_KEY in .env"
                )
            raise ModelConnectionError(
                "Gemini vision stream request failed",
                details=err_msg,
            )


# ============================================================
# Model Router Factory
# ============================================================


class ModelRouter:
    """
    Routes prompts to the appropriate model provider based on settings.

    Supports conversation context via the `context` parameter,
    optional caching, and async generation.

    Usage:
        router = ModelRouter(settings)
        response = router.generate("Hello!")
        response = await router.generate_async("Hello!")
    """

    _PROVIDER_MAP = {
        PROVIDER_MOCK: MockModel,
        PROVIDER_OLLAMA: OllamaModel,
        PROVIDER_OPENAI: OpenAIModel,
        PROVIDER_GEMINI: GeminiModel,
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
        # Initialize token counter for the active model
        self._token_counter = TokenCounter.for_model(self.model.model_name)
        # Initialize rate limiter from settings
        self._rate_limiter = RateLimiter(
            max_requests=settings.rate_limit_requests,
            max_tokens=settings.rate_limit_tokens,
            window_seconds=60,
        )
        # Health check cache
        self._health_cache: dict[str, dict] = {}
        self._health_cache_time: float = 0.0
        self._health_cache_ttl: float = 30.0  # 30 seconds
        logger.info(
            f"ModelRouter initialized: "
            f"provider={settings.model_provider}, "
            f"model={self.model.model_name}, "
            f"cache_ttl={cache_ttl}s, "
            f"rate_limit={settings.rate_limit_requests} req/min, "
            f"token_count={type(self._token_counter).__name__}"
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
        Send a prompt to the configured model (sync).

        Args:
            prompt: The input text
            context: Optional conversation history
            use_cache: Whether to check and store in response cache
            **kwargs: Additional parameters passed to the underlying model

        Returns:
            ModelResponse with the generated text
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        # Check cache first (skip for Mock)
        if use_cache and self.settings.model_provider != PROVIDER_MOCK:
            cache_key = make_model_cache_key(prompt, context, self.model.model_name)
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Model response cache HIT")
                return cached

        # Estimate prompt tokens
        prompt_tokens = self._token_counter.count_tokens(prompt)
        if context:
            prompt_tokens += self._token_counter.count_messages(context)

        ctx_info = f", context={len(context)} messages" if context else ""
        logger.debug(f"Routing prompt (~{prompt_tokens}t{ctx_info}) to {self.model}")

        # Rate limit check — wait_if_needed() automatically records the request
        if self.settings.model_provider != PROVIDER_MOCK:
            self._rate_limiter.wait_if_needed(tokens=prompt_tokens)

        response = self.model.generate(prompt, context=context, **kwargs)

        # Log token usage (no extra record — wait_if_needed already accounted for the call)
        response_tokens = response.tokens_used or self._token_counter.count_tokens(response.text)
        total_estimated = prompt_tokens + response_tokens
        logger.debug(
            f"Model response: in={prompt_tokens}t out={response_tokens}t "
            f"~total={total_estimated}t, {response.latency_ms:.0f}ms latency"
        )

        # Store in cache (skip Mock)
        if use_cache and self.settings.model_provider != PROVIDER_MOCK:
            cache_key = make_model_cache_key(prompt, context, self.model.model_name)
            self._cache.set(cache_key, response)

        return response

    async def generate_async(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt to the configured model asynchronously (non-blocking).

        Uses aiohttp for Ollama/OpenAI, asyncio.sleep for Mock.
        Falls back to thread pool if the model doesn't have true async support.

        Args:
            prompt: The input text
            context: Optional conversation history
            use_cache: Whether to check and store in response cache
            **kwargs: Additional parameters passed to the underlying model

        Returns:
            ModelResponse with the generated text
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        # Check cache first (skip for Mock)
        if use_cache and self.settings.model_provider != PROVIDER_MOCK:
            cache_key = make_model_cache_key(prompt, context, self.model.model_name)
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("Model response cache HIT (async)")
                return cached

        # Estimate prompt tokens
        prompt_tokens = self._token_counter.count_tokens(prompt)
        if context:
            prompt_tokens += self._token_counter.count_messages(context)

        ctx_info = f", context={len(context)} messages" if context else ""
        logger.debug(f"Routing async prompt (~{prompt_tokens}t{ctx_info}) to {self.model}")

        # Rate limit check — async_wait_if_needed() automatically records the request
        if self.settings.model_provider != PROVIDER_MOCK:
            await self._rate_limiter.async_wait_if_needed(tokens=prompt_tokens)

        response = await self.model.async_generate(prompt, context=context, **kwargs)

        # Log token usage (no extra record — wait_if_needed already accounted)
        response_tokens = response.tokens_used or self._token_counter.count_tokens(response.text)
        total_estimated = prompt_tokens + response_tokens
        logger.debug(
            f"Async response: in={prompt_tokens}t out={response_tokens}t "
            f"~total={total_estimated}t, {response.latency_ms:.0f}ms latency"
        )

        # Store in cache (skip Mock)
        if use_cache and self.settings.model_provider != PROVIDER_MOCK:
            cache_key = make_model_cache_key(prompt, context, self.model.model_name)
            self._cache.set(cache_key, response)

        return response

    async def generate_stream(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        use_cache: bool = True,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from the configured model (async generator).

        Yields individual tokens as they arrive from the model (SSE).
        Mock model yields words with delays for visual effect.
        Ollama/OpenAI yield real streaming tokens.

        Args:
            prompt: The input text
            context: Optional conversation history
            use_cache: Whether to check cache (streaming skips cache)
            **kwargs: Additional parameters

        Yields:
            str: Individual response tokens
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        logger.debug(f"Streaming prompt ({len(prompt)} chars) to {self.model}")
        async for token in self.model.generate_stream(prompt, context=context, **kwargs):
            yield token

    def generate_with_fallback(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        use_cache: bool = True,
        fallback_order: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Dynamic Model Fallback (Feature 2).

        Tries multiple providers in order. If the primary provider fails
        (connection error, timeout, invalid key), automatically falls back
        to the next provider in the fallback_order list.

        The default fallback order is: [current, "mock"] — i.e., try the
        configured provider, then fall back to mock if it fails.

        User can specify: ["openai", "gemini", "ollama", "mock"]

        Args:
            prompt: The input text
            context: Optional conversation history
            use_cache: Whether to check response cache
            fallback_order: Ordered list of provider names to try
            **kwargs: Additional parameters

        Returns:
            ModelResponse with provider info (check response.provider)
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        fallback_order = fallback_order or [
            self.settings.model_provider,
            PROVIDER_MOCK,
        ]

        errors = []
        for provider_name in fallback_order:
            try:
                # Try the next provider
                response = self.generate_with_provider(
                    provider_name, prompt, context=context, **kwargs
                )
                if response.text and response.text.strip():
                    logger.info(
                        f"Fallback: succeeded with provider={provider_name}"
                    )
                    return response
            except (ModelConnectionError, ConfigurationError) as e:
                errors.append(f"{provider_name}: {e}")
                logger.warning(f"Fallback: {provider_name} failed: {e}")
                continue
            except Exception as e:
                errors.append(f"{provider_name}: {e}")
                logger.warning(f"Fallback: {provider_name} unexpected error: {e}")
                continue

        # All providers failed
        raise ModelConnectionError(
            "All providers failed in fallback chain",
            details="; ".join(errors),
        )

    def clear_cache(self) -> int:
        """Clear the model response cache. Returns number of entries cleared."""
        return self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Get model cache statistics."""
        return self._cache.get_stats()

    def get_rate_limiter_stats(self) -> dict:
        """Get rate limiter usage statistics."""
        return self._rate_limiter.get_current_usage()

    def get_token_count(self, text: str) -> int:
        """Count tokens in text using the active model's tokenizer."""
        return self._token_counter.count_tokens(text)

    def check_all_providers(self, force: bool = False) -> list[dict]:
        """
        Check health of ALL supported providers.

        Results are cached for `_health_cache_ttl` seconds (default 30).
        Pass force=True to bypass cache.

        Returns a list of dicts, each with keys:
            provider, ok, latency_ms, error, model
        """
        now = time.time()
        if not force and self._health_cache and (now - self._health_cache_time) < self._health_cache_ttl:
            return list(self._health_cache.values())

        results: list[dict] = []
        settings = self.settings

        for provider_name, model_class in self._PROVIDER_MAP.items():
            try:
                # Create a temporary instance for health check
                # For the current provider, reuse the existing model
                if provider_name == settings.model_provider:
                    model = self.model
                else:
                    # Temporarily switch settings
                    temp_settings = Settings(
                        model_provider=provider_name,
                        ollama_url=settings.ollama_url,
                        ollama_model=settings.ollama_model,
                        openai_api_key=settings.openai_api_key,
                        openai_model=settings.openai_model,
                        gemini_api_key=settings.gemini_api_key,
                        gemini_model=settings.gemini_model,
                    )
                    model = model_class(temp_settings)

                result = model.check_health()
                results.append(result)
            except Exception as e:
                results.append({
                    "provider": provider_name,
                    "ok": False,
                    "latency_ms": 0.0,
                    "error": str(e)[:100],
                    "model": provider_name,
                })

        # Cache results
        self._health_cache = {r["provider"]: r for r in results}
        self._health_cache_time = now

        return results

    def generate_with_provider(
        self,
        provider_name: str,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate a response using a SPECIFIC provider, temporarily overriding
        the current configured provider. The ModelRouter's active provider is
        restored after the call.

        Used by SmartRouter for multi-model conversations where each message
        may be routed to a different provider.

        Args:
            provider_name: Target provider (e.g. 'ollama', 'openai', 'gemini')
            prompt: The input text
            context: Optional conversation history
            **kwargs: Additional parameters

        Returns:
            ModelResponse with provider info
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        # Get the model class for the target provider
        model_class = self._PROVIDER_MAP.get(provider_name)
        if model_class is None:
            raise AssistantError(
                f"Unknown provider '{provider_name}'. "
                f"Supported: {', '.join(sorted(self._PROVIDER_MAP.keys()))}"
            )

        # Check if the target provider has required credentials
        if provider_name == PROVIDER_OPENAI and not self.settings.openai_api_key:
            logger.warning(f"OpenAI key not configured, falling back to {self.settings.model_provider}")
            return self.generate(prompt, context=context, **kwargs)
        if provider_name == PROVIDER_GEMINI and not self.settings.gemini_api_key:
            logger.warning(f"Gemini key not configured, falling back to {self.settings.model_provider}")
            return self.generate(prompt, context=context, **kwargs)

        # Create temporary model for the target provider
        old_provider = self.settings.model_provider
        self.settings.model_provider = provider_name

        try:
            temp_model = model_class(self.settings)
            # Use the temp model's own rate limiter approach (skip if Mock)
            logger.debug(f"SmartRouter: routing to {provider_name} (model={temp_model.model_name})")

            if provider_name == PROVIDER_MOCK:
                response = temp_model.generate(prompt, context=context, **kwargs)
            else:
                prompt_tokens = self._token_counter.count_tokens(prompt)
                if context:
                    prompt_tokens += self._token_counter.count_messages(context)
                self._rate_limiter.wait_if_needed(tokens=prompt_tokens)
                response = temp_model.generate(prompt, context=context, **kwargs)

            return response
        except Exception as e:
            logger.warning(f"SmartRouter: {provider_name} failed ({e}), falling back to {old_provider}")
            self.settings.model_provider = old_provider
            return self.generate(prompt, context=context, **kwargs)
        finally:
            self.settings.model_provider = old_provider

    async def generate_with_provider_async(
        self,
        provider_name: str,
        prompt: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Generate a response using a SPECIFIC provider (async version).

        Temporarily creates a model instance for the target provider and calls
        its async_generate method. Falls back to the default provider on failure.

        Used by SmartRouter for multi-model conversations where each message
        may be routed to a different provider.

        Args:
            provider_name: Target provider (e.g. 'ollama', 'openai', 'gemini')
            prompt: The input text
            context: Optional conversation history
            **kwargs: Additional parameters

        Returns:
            ModelResponse with provider info
        """
        if not prompt or not prompt.strip():
            raise AssistantError("Prompt cannot be empty")

        # Get the model class for the target provider
        model_class = self._PROVIDER_MAP.get(provider_name)
        if model_class is None:
            raise AssistantError(
                f"Unknown provider '{provider_name}'. "
                f"Supported: {', '.join(sorted(self._PROVIDER_MAP.keys()))}"
            )

        # Check if the target provider has required credentials
        if provider_name == PROVIDER_OPENAI and not self.settings.openai_api_key:
            logger.warning(f"OpenAI key not configured, falling back to {self.settings.model_provider}")
            return await self.generate_async(prompt, context=context, **kwargs)
        if provider_name == PROVIDER_GEMINI and not self.settings.gemini_api_key:
            logger.warning(f"Gemini key not configured, falling back to {self.settings.model_provider}")
            return await self.generate_async(prompt, context=context, **kwargs)

        # Create temporary model for the target provider
        old_provider = self.settings.model_provider
        self.settings.model_provider = provider_name

        try:
            temp_model = model_class(self.settings)
            logger.debug(f"SmartRouter: routing async to {provider_name} (model={temp_model.model_name})")

            if provider_name == PROVIDER_MOCK:
                response = await temp_model.async_generate(prompt, context=context, **kwargs)
            else:
                prompt_tokens = self._token_counter.count_tokens(prompt)
                if context:
                    prompt_tokens += self._token_counter.count_messages(context)
                await self._rate_limiter.async_wait_if_needed(tokens=prompt_tokens)
                response = await temp_model.async_generate(prompt, context=context, **kwargs)

            return response
        except Exception as e:
            logger.warning(f"SmartRouter: {provider_name} async failed ({e}), falling back to {old_provider}")
            return await self.generate_async(prompt, context=context, **kwargs)
        finally:
            self.settings.model_provider = old_provider

    def generate_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> ModelResponse:
        """
        Send a prompt with an image to the configured model (vision).

        Forwards to the model's generate_with_image method.
        If the current provider supports vision (OpenAI, Gemini, Ollama with
        vision models, Mock), it processes the image. Otherwise falls back
        to text-only generation with a note.

        Args:
            prompt: Text prompt describing the image
            image_base64: Base64 data URI of the image
            context: Optional conversation history
            **kwargs: Additional parameters

        Returns:
            ModelResponse with vision analysis
        """
        if not prompt and not image_base64:
            raise AssistantError("Prompt or image required")

        logger.debug(f"Vision request ({len(prompt)} chars) to {self.model}")
        return self.model.generate_with_image(prompt, image_base64, context=context, **kwargs)

    async def generate_stream_with_image(
        self,
        prompt: str,
        image_base64: str,
        context: Optional[list[dict]] = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Stream tokens from a vision model (async generator).

        Yields individual tokens as they arrive from the vision model's
        streaming endpoint. Supports Mock, Ollama (SSE), OpenAI (SSE),
        and Gemini (stream=True) vision streaming.

        Args:
            prompt: Text prompt describing the image
            image_base64: Base64 data URI of the image
            context: Optional conversation history
            **kwargs: Additional parameters

        Yields:
            str: Individual response tokens from the vision model
        """
        if not prompt and not image_base64:
            raise AssistantError("Prompt or image required")

        logger.debug(f"Vision streaming request ({len(prompt)} chars) to {self.model}")
        async for token in self.model.generate_stream_with_image(
            prompt, image_base64, context=context, **kwargs
        ):
            yield token

    def count_prompt_tokens(self, prompt: str, context: Optional[list[dict]] = None) -> dict:
        """Get detailed token usage report for a prompt + context."""
        prompt_t = self._token_counter.count_tokens(prompt)
        ctx_t = self._token_counter.count_messages(context) if context else 0
        return {
            "prompt_tokens": prompt_t,
            "context_tokens": ctx_t,
            "total_input_tokens": prompt_t + ctx_t,
        }

    def __repr__(self) -> str:
        return f"ModelRouter(provider={self.settings.model_provider}, model={self.model})"
