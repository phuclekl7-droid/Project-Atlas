"""
Unit tests for vision streaming (generate_stream_with_image).

Tests:
- BaseModel.generate_stream_with_image default fallback
- MockModel.generate_stream_with_image (word-by-word streaming)
- OllamaModel.generate_stream_with_image (SSE with images)
- OpenAIModel.generate_stream_with_image (SSE with vision content array)
- GeminiModel.generate_stream_with_image (stream=True with inline_data)
- ModelRouter.generate_stream_with_image factory
- Error handling in vision streaming
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.core import AssistantError, ModelConnectionError
from src.model_router import ModelResponse, ModelRouter
from src.settings import PROVIDER_MOCK, Settings

# ── Test base64 image data URI ──
TEST_IMAGE_B64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="


# ============================================================
# BaseModel Vision Stream Tests
# ============================================================


class TestBaseModelVisionStream:
    def test_default_fallback_yields_full_text(self):
        """BaseModel.generate_stream_with_image should yield full text as one token."""
        from src.model_router import BaseModel

        class DummyModel(BaseModel):
            def _get_model_name(self):
                return "dummy"

            def generate(self, prompt, context=None, **kwargs):
                return ModelResponse(text="vision result", model_name="dummy", provider="mock")

        settings = Settings(model_provider=PROVIDER_MOCK)
        model = DummyModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream_with_image("desc", TEST_IMAGE_B64):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) == 1
        assert "vision result" in tokens[0]

    def test_default_fallback_uses_async_generate_with_image(self):
        """Default should delegate to async_generate_with_image."""
        from src.model_router import BaseModel

        class TrackingModel(BaseModel):
            def _get_model_name(self):
                return "track"

            def generate(self, prompt, context=None, **kwargs):
                return ModelResponse(text="ok", model_name="track", provider="mock")

            async def async_generate_with_image(self, prompt, image_base64, context=None, **kwargs):
                return ModelResponse(text="async_via_image", model_name="track", provider="mock")

        settings = Settings(model_provider=PROVIDER_MOCK)
        model = TrackingModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream_with_image("desc", TEST_IMAGE_B64):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert "async_via_image" in tokens[0]


# ============================================================
# MockModel Vision Stream Tests
# ============================================================


class TestMockModelVisionStream:
    def test_stream_yields_words(self):
        """Mock vision stream should yield multiple tokens (words)."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream_with_image(
                "What is in this image?", TEST_IMAGE_B64
            ):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) > 1  # Should yield multiple words
        assert all(isinstance(t, str) for t in tokens)
        assert any(" " in t for t in tokens)  # Spaces at word ends

    def test_stream_uses_asyncio_sleep(self):
        """Mock vision stream should use asyncio.sleep between words."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def measure():
            start = time.time()
            async for _ in model.generate_stream_with_image("desc", TEST_IMAGE_B64):
                pass
            return time.time() - start

        elapsed = asyncio.run(measure())
        assert elapsed > 0.01

    def test_stream_contains_vision_keywords(self):
        """Mock vision stream should mention vision/mock in its output."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def collect():
            tokens = []
            async for token in model.generate_stream_with_image("desc", TEST_IMAGE_B64):
                tokens.append(token)
            return "".join(tokens)

        text = asyncio.run(collect())
        assert "Mock" in text
        assert "Vision" in text or "vision" in text.lower()

    def test_stream_with_context(self):
        """Mock vision stream should handle context messages."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)
        context = [{"role": "user", "content": "What was my last question?"}]

        async def collect():
            tokens = []
            async for token in model.generate_stream_with_image(
                "desc", TEST_IMAGE_B64, context=context
            ):
                tokens.append(token)
            return "".join(tokens)

        text = asyncio.run(collect())
        assert len(text) > 0
        # Should include context count info (Mock's vision response mentions context)
        assert "Context" in text or "context" in text.lower()


# ============================================================
# ModelRouter Vision Stream Tests
# ============================================================


class TestModelRouterVisionStream:
    def test_router_vision_stream_mock(self):
        """ModelRouter.generate_stream_with_image should work with Mock."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        async def collect():
            tokens = []
            async for token in router.generate_stream_with_image(
                "Describe this image", TEST_IMAGE_B64
            ):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) > 1
        assert "Mock" in "".join(tokens)

    def test_router_vision_stream_empty_input(self):
        """Empty prompt and image should raise AssistantError."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        async def test():
            with pytest.raises(AssistantError, match="required"):
                async for _ in router.generate_stream_with_image("", ""):
                    pass

        asyncio.run(test())

    def test_router_vision_stream_empty_prompt_with_image(self):
        """Empty prompt with valid image should still work (Mock fallback)."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)

        async def collect():
            tokens = []
            async for token in router.generate_stream_with_image(
                "", TEST_IMAGE_B64
            ):
                tokens.append(token)
            return "".join(tokens)

        text = asyncio.run(collect())
        assert len(text) > 0

    def test_router_vision_stream_context(self):
        """Router vision stream should pass context through."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)
        context = [{"role": "user", "content": "Previous message"}]

        async def collect():
            tokens = []
            async for token in router.generate_stream_with_image(
                "desc", TEST_IMAGE_B64, context=context
            ):
                tokens.append(token)
            return "".join(tokens)

        text = asyncio.run(collect())
        assert len(text) > 0


# ============================================================
# Real Provider Vision Stream Tests (mocked network)
# ============================================================


class TestOllamaVisionStreamMock:
    """Test Ollama vision streaming with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_ollama_vision_stream_parses_sse(self):
        """Ollama vision stream should parse SSE lines and yield tokens."""
        from src.model_router import OllamaModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            ollama_url="http://localhost:11434",
        )
        model = OllamaModel(settings)

        # Mock aiohttp response that yields SSE lines
        mock_response = AsyncMock()
        mock_response.status = 200

        sse_lines = [
            b'{"message":{"content":"This "},"done":false}\n',
            b'{"message":{"content":"is "},"done":false}\n',
            b'{"message":{"content":"a "},"done":false}\n',
            b'{"message":{"content":"cat "},"done":false}\n',
            b'{"message":{"content":"in an image"},"done":true}\n',
        ]

        async def mock_content():
            for line in sse_lines:
                yield line

        mock_response.content = mock_content()

        # Mock the session.post to return our mock response
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession", return_value=mock_session):
            tokens = []
            async for token in model.generate_stream_with_image(
                "What is this?", TEST_IMAGE_B64
            ):
                tokens.append(token)

        assert len(tokens) == 4  # "This ", "is ", "a ", "cat "
        combined = "".join(tokens)
        assert "This" in combined
        assert "cat" in combined

    @pytest.mark.asyncio
    async def test_ollama_vision_stream_connection_error(self):
        """Ollama vision stream should raise on connection error."""
        from src.model_router import OllamaModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            ollama_url="http://localhost:99999",
        )
        model = OllamaModel(settings)

        with pytest.raises(ModelConnectionError, match="Cannot connect"):
            async for _ in model.generate_stream_with_image(
                "desc", TEST_IMAGE_B64
            ):
                pass

    @pytest.mark.asyncio
    async def test_ollama_vision_stream_http_error(self):
        """Ollama vision stream should raise on non-200 status."""
        from src.model_router import OllamaModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            ollama_url="http://localhost:11434",
        )
        model = OllamaModel(settings)

        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request")

        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with pytest.raises(ModelConnectionError, match="400"):
                async for _ in model.generate_stream_with_image(
                    "desc", TEST_IMAGE_B64
                ):
                    pass

    @pytest.mark.asyncio
    async def test_ollama_vision_stream_empty_image_path(self):
        """Ollama should strip data URI prefix for raw base64 in images array."""
        from src.model_router import OllamaModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            ollama_url="http://localhost:11434",
        )
        model = OllamaModel(settings)

        # Intercept the payload to verify images array
        mock_response = AsyncMock()
        mock_response.status = 200

        async def mock_content():
            yield b'{"message":{"content":"OK"},"done":true}\n'

        mock_response.content = mock_content()

        posted_payloads = []

        async def capture_post(url, json=None, **kw):
            posted_payloads.append(json)
            mock_resp = AsyncMock()
            mock_resp.status = 200
            async def mc():
                yield b'{"message":{"content":"OK"},"done":true}\n'
            mock_resp.content = mc()
            return mock_resp

        mock_session = AsyncMock()
        mock_session.post = capture_post

        with patch("aiohttp.ClientSession", return_value=mock_session):
            async for _ in model.generate_stream_with_image("desc", TEST_IMAGE_B64):
                pass

        assert len(posted_payloads) == 1
        payload = posted_payloads[0]
        assert payload["stream"] is True
        # Check images array contains raw base64 (no data:image/...;base64, prefix)
        images = payload["messages"][-1].get("images", [])
        assert len(images) == 1
        assert "iVBOR" in images[0]
        assert "data:" not in images[0]


class TestOpenAIVisionStreamMock:
    """Test OpenAI vision streaming with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_openai_vision_stream_parses_sse(self):
        """OpenAI vision stream should parse SSE 'data:' lines."""
        from src.model_router import OpenAIModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            openai_api_key="sk-test123",
        )
        model = OpenAIModel(settings)

        sse_lines = [
            b'data: {"choices":[{"delta":{"content":"The "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"image "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"shows "}}]}\n\n',
            b'data: {"choices":[{"delta":{"content":"a sunset"}}]}\n\n',
            b'data: [DONE]\n\n',
        ]

        mock_response = AsyncMock()
        mock_response.status = 200

        async def mock_content():
            for line in sse_lines:
                yield line

        mock_response.content = mock_content()

        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__.return_value = mock_response

        with patch("aiohttp.ClientSession", return_value=mock_session):
            tokens = []
            async for token in model.generate_stream_with_image(
                "Describe", TEST_IMAGE_B64
            ):
                tokens.append(token)

        assert len(tokens) == 4
        combined = "".join(tokens)
        assert "sunset" in combined
        assert "shows" in combined

    @pytest.mark.asyncio
    async def test_openai_vision_stream_no_api_key(self):
        """OpenAI vision stream without API key should raise."""
        from src.model_router import OpenAIModel
        from src.core import ConfigurationError
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            openai_api_key="",
        )
        model = OpenAIModel(settings)

        with pytest.raises(ConfigurationError, match="API key"):
            async for _ in model.generate_stream_with_image(
                "desc", TEST_IMAGE_B64
            ):
                pass

    @pytest.mark.asyncio
    async def test_openai_vision_stream_builds_content_array(self):
        """OpenAI vision stream should build content array with text + image_url."""
        from src.model_router import OpenAIModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            openai_api_key="sk-test123",
        )
        model = OpenAIModel(settings)

        posted_payloads = []

        async def capture_post(url, json=None, **kw):
            posted_payloads.append(json)
            mock_resp = AsyncMock()
            mock_resp.status = 200
            async def mc():
                yield b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                yield b'data: [DONE]\n\n'
            mock_resp.content = mc()
            return mock_resp

        mock_session = AsyncMock()
        mock_session.post = capture_post

        with patch("aiohttp.ClientSession", return_value=mock_session):
            async for _ in model.generate_stream_with_image("Describe this", TEST_IMAGE_B64):
                pass

        assert len(posted_payloads) == 1
        payload = posted_payloads[0]
        assert payload["stream"] is True
        assert payload["max_tokens"] == 4096
        # Check content array format
        last_msg = payload["messages"][-1]
        assert isinstance(last_msg["content"], list)
        assert last_msg["content"][0]["type"] == "text"
        assert last_msg["content"][0]["text"] == "Describe this"
        assert last_msg["content"][1]["type"] == "image_url"


class TestGeminiVisionStreamMock:
    """Test Gemini vision streaming with mocked responses."""

    @pytest.mark.asyncio
    async def test_gemini_vision_stream_yields_chunks(self):
        """Gemini vision stream should yield text from streaming chunks."""
        from src.model_router import GeminiModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            gemini_api_key="test-key",
        )
        model = GeminiModel(settings)

        # Create mock chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "This "
        mock_chunk2 = MagicMock()
        mock_chunk2.text = "is "
        mock_chunk3 = MagicMock()
        mock_chunk3.text = "a majestic mountain"

        # Mock the generative model response
        mock_response = [mock_chunk1, mock_chunk2, mock_chunk3]

        # Mock genai
        mock_genai = MagicMock()
        mock_genai.configure.return_value = None

        mock_gen_model = MagicMock()
        mock_gen_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_gen_model

        model._genai = mock_genai

        tokens = []
        async for token in model.generate_stream_with_image(
            "Describe this landscape", TEST_IMAGE_B64
        ):
            tokens.append(token)

        assert len(tokens) == 3
        combined = "".join(tokens)
        assert "majestic mountain" in combined

    @pytest.mark.asyncio
    async def test_gemini_vision_stream_skips_empty_chunks(self):
        """Gemini vision stream should skip empty chunks gracefully."""
        from src.model_router import GeminiModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            gemini_api_key="test-key",
        )
        model = GeminiModel(settings)

        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Valid"
        mock_chunk2 = MagicMock()
        # Simulate chunk that raises exception on .text access
        type(mock_chunk2).text = PropertyMock(side_effect=Exception("Empty"))

        mock_response = [mock_chunk1, mock_chunk2]

        mock_genai = MagicMock()
        mock_genai.configure.return_value = None

        mock_gen_model = MagicMock()
        mock_gen_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_gen_model

        model._genai = mock_genai

        tokens = []
        async for token in model.generate_stream_with_image(
            "desc", TEST_IMAGE_B64
        ):
            tokens.append(token)

        assert len(tokens) == 1
        assert tokens[0] == "Valid"

    @pytest.mark.asyncio
    async def test_gemini_vision_stream_with_context(self):
        """Gemini vision stream with chat history should use start_chat."""
        from src.model_router import GeminiModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            gemini_api_key="test-key",
        )
        model = GeminiModel(settings)

        context = [{"role": "user", "content": "Previous question"}]

        mock_chunk = MagicMock()
        mock_chunk.text = "Answer with context"

        mock_chat = MagicMock()
        mock_chat.send_message.return_value = [mock_chunk]

        mock_genai = MagicMock()
        mock_genai.configure.return_value = None

        mock_gen_model = MagicMock()
        mock_gen_model.start_chat.return_value = mock_chat
        mock_genai.GenerativeModel.return_value = mock_gen_model

        model._genai = mock_genai

        tokens = []
        async for token in model.generate_stream_with_image(
            "desc", TEST_IMAGE_B64, context=context
        ):
            tokens.append(token)

        # Verify start_chat was called with history
        mock_gen_model.start_chat.assert_called_once()
        assert len(tokens) >= 1
        assert "context" in "".join(tokens)


# ============================================================
# Integration Tests: Mock vision streaming end-to-end
# ============================================================


class TestVisionStreamIntegration:
    def test_vision_stream_returns_full_text_equivalent_to_sync(self):
        """Streamed vision text should equal sync vision text."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def compare():
            # Get sync response
            sync_resp = model.generate_with_image("Describe", TEST_IMAGE_B64)
            sync_text = sync_resp.text.strip()

            # Get streamed response
            tokens = []
            async for token in model.generate_stream_with_image("Describe", TEST_IMAGE_B64):
                tokens.append(token)
            streamed_text = "".join(tokens).strip()

            # Mock adds trailing spaces to words via streaming, normalize
            assert sync_text.replace(" ", "") == streamed_text.replace(" ", "")
            return True

        assert asyncio.run(compare())

    def test_vision_stream_router_to_memory_flow(self, memory):
        """Simulate the UI flow: stream vision → save to memory."""
        settings = Settings(model_provider=PROVIDER_MOCK)
        router = ModelRouter(settings)
        session_id = memory.create_session()

        # Add user message with image reference
        from src.memory import Message
        img_content = Message.make_image_content("test.png", "What is this?")
        memory.add_message(session_id, "user", img_content)

        async def stream_and_save():
            context = memory.get_context(session_id, limit=10)
            tokens = []
            async for token in router.generate_stream_with_image(
                prompt="What is this?",
                image_base64=TEST_IMAGE_B64,
                context=context,
            ):
                tokens.append(token)
            final_text = "".join(tokens)
            memory.add_message(session_id, "assistant", final_text, provider=PROVIDER_MOCK)
            return final_text

        text = asyncio.run(stream_and_save())
        assert len(text) > 0

        # Verify both messages saved
        messages = memory.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert len(messages[1].content) > 0

    def test_vision_stream_multiple_calls(self):
        """Multiple vision streams in sequence should work."""
        from src.model_router import MockModel
        settings = Settings(model_provider=PROVIDER_MOCK)
        model = MockModel(settings)

        async def run_sequential():
            results = []
            for desc in ["First image", "Second image", "Third image"]:
                tokens = []
                async for token in model.generate_stream_with_image(desc, TEST_IMAGE_B64):
                    tokens.append(token)
                results.append("".join(tokens))
            return results

        results = asyncio.run(run_sequential())
        assert len(results) == 3
        for r in results:
            assert "Mock" in r

    @pytest.mark.asyncio
    async def test_vision_stream_ollama_payload_structure(self):
        """Verify the Ollama vision streaming payload structure."""
        from src.model_router import OllamaModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            ollama_url="http://localhost:11434",
            ollama_model="llava",
        )
        model = OllamaModel(settings)

        posted_payloads = []

        async def capture_post(url, json=None, **kw):
            posted_payloads.append(json)
            mock_resp = AsyncMock()
            mock_resp.status = 200
            async def mc():
                yield b'{"message":{"content":"ok"},"done":true}\n'
            mock_resp.content = mc()
            return mock_resp

        mock_session = AsyncMock()
        mock_session.post = capture_post

        with patch("aiohttp.ClientSession", return_value=mock_session):
            async for _ in model.generate_stream_with_image("desc", TEST_IMAGE_B64):
                pass

        assert len(posted_payloads) == 1
        payload = posted_payloads[0]
        assert payload["model"] == "llava"
        assert payload["stream"] is True
        assert len(payload["messages"][-1]["images"]) == 1

    @pytest.mark.asyncio
    async def test_gemini_vision_stream_data_uri_parsing(self):
        """Gemini vision stream should parse mime_type from data URI."""
        from src.model_router import GeminiModel
        settings = Settings(
            model_provider=PROVIDER_MOCK,
            gemini_api_key="test-key",
        )
        model = GeminiModel(settings)

        # Track what was passed to generate_content
        posted_content = []

        mock_chunk = MagicMock()
        mock_chunk.text = "Analysis"

        mock_genai = MagicMock()
        mock_genai.configure.return_value = None

        mock_gen_model = MagicMock()

        def track_content(content, stream=True, **kw):
            posted_content.append(content)
            return [mock_chunk]

        mock_gen_model.generate_content = track_content
        mock_genai.GenerativeModel.return_value = mock_gen_model

        model._genai = mock_genai

        # Test with different mime types
        jpeg_b64 = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
        async for _ in model.generate_stream_with_image("desc", jpeg_b64):
            pass

        assert len(posted_content) == 1
        content_parts = posted_content[0]
        assert len(content_parts) == 2
        assert content_parts[0] == "desc"
        assert content_parts[1]["mime_type"] == "image/jpeg"


