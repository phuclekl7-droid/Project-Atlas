""""
Unit tests for GeminiModel.

Tests:
- GeminiModel initialization and configuration
- API key validation
- Context conversion (OpenAI format → Gemini format)
- Sync generate with mocked genai
- Async generate with mocked genai
- Streaming with mocked genai
- Error handling
- Provider mapping in ModelRouter
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.core import AssistantError, ConfigurationError, ModelConnectionError
from src.model_router import ModelResponse, ModelRouter
from src.settings import PROVIDER_GEMINI, Settings


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def gemini_settings():
    """Settings with Gemini provider and a fake API key."""
    return Settings(
        model_provider=PROVIDER_GEMINI,
        gemini_api_key="AIzaSy-test-fake-key-12345",
        gemini_model="gemini-2.0-flash",
    )


# ============================================================
# GeminiModel Initialization Tests
# ============================================================


class TestGeminiModelInit:
    def test_model_name_from_settings(self, gemini_settings):
        """Model name should come from settings.gemini_model."""
        from src.model_router import GeminiModel
        model = GeminiModel(gemini_settings)
        assert model.model_name == "gemini-2.0-flash"

    def test_no_api_key_raises_on_generate(self):
        """Missing API key should raise ConfigurationError on generate, not init."""
        from src.model_router import GeminiModel
        settings = Settings(model_provider=PROVIDER_GEMINI, gemini_api_key="")
        model = GeminiModel(settings)

        with pytest.raises(ConfigurationError, match="API key"):
            model.generate("Hello!")

    def test_repr(self, gemini_settings):
        """__repr__ should show class name and model."""
        from src.model_router import GeminiModel
        model = GeminiModel(gemini_settings)
        r = repr(model)
        assert "GeminiModel" in r
        assert "gemini-2.0-flash" in r


# ============================================================
# Context Conversion Tests
# ============================================================


class TestContextConversion:
    def test_convert_empty_context_returns_none(self, gemini_settings):
        """Empty context should return None."""
        from src.model_router import GeminiModel
        model = GeminiModel(gemini_settings)
        assert model._convert_context(None) is None
        assert model._convert_context([]) is None

    def test_convert_single_user_message(self, gemini_settings):
        """A single user message should convert correctly."""
        from src.model_router import GeminiModel
        model = GeminiModel(gemini_settings)
        context = [{"role": "user", "content": "Hello!"}]
        result = model._convert_context(context)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["parts"] == [{"text": "Hello!"}]

    def test_convert_assistant_to_model_role(self, gemini_settings):
        """Assistant role should be converted to 'model' role."""
        from src.model_router import GeminiModel
        model = GeminiModel(gemini_settings)
        context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = model._convert_context(context)
        assert len(result) == 2
        assert result[1]["role"] == "model"  # NOT "assistant"
        assert result[1]["parts"] == [{"text": "Hi!"}]

    def test_convert_multi_turn(self, gemini_settings):
        """Multi-turn conversation should convert all messages."""
        from src.model_router import GeminiModel
        model = GeminiModel(gemini_settings)
        context = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ]
        result = model._convert_context(context)
        assert len(result) == 3
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "model"
        assert result[2]["role"] == "user"


# ============================================================
# GeminiModel Generate Tests (mocked)
# ============================================================


class TestGeminiModelGenerate:
    def test_generate_simple_prompt(self, gemini_settings):
        """Sync generate should return a ModelResponse for simple prompts."""
        from src.model_router import GeminiModel

        # Mock the genai response
        mock_candidate = MagicMock()
        mock_candidate.content.parts[0].text = "Hello from Gemini!"
        mock_candidate.finish_reason = 1  # STOP

        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini!"
        mock_response.candidates = [mock_candidate]
        mock_response.prompt_feedback = None
        type(mock_response).usage_metadata = PropertyMock(return_value=None)

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai  # Inject mock

        result = model.generate("Hello!")
        assert isinstance(result, ModelResponse)
        assert result.text == "Hello from Gemini!"
        assert result.provider == PROVIDER_GEMINI
        assert result.model_name == "gemini-2.0-flash"
        assert result.latency_ms >= 0

    def test_generate_with_context(self, gemini_settings):
        """Sync generate with context should use chat mode."""
        from src.model_router import GeminiModel

        mock_chat = MagicMock()
        mock_chat.send_message.return_value.text = "Gemini response with context"
        mock_chat.send_message.return_value.candidates = [
            MagicMock(content=MagicMock(parts=[MagicMock(text="Gemini response with context")]))
        ]
        mock_chat.send_message.return_value.candidates[0].finish_reason = 1
        mock_chat.send_message.return_value.prompt_feedback = None

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.start_chat.return_value = mock_chat

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai  # Inject mock

        context = [{"role": "user", "content": "Previous message"}]
        result = model.generate("Hello!", context=context)
        assert isinstance(result, ModelResponse)
        assert result.text == "Gemini response with context"
        assert result.provider == PROVIDER_GEMINI

        # Verify chat was started with history
        mock_genai.GenerativeModel.return_value.start_chat.assert_called_once()
        chat_kwargs = mock_genai.GenerativeModel.return_value.start_chat.call_args.kwargs
        assert "history" in chat_kwargs

    def test_generate_empty_response(self, gemini_settings):
        """Empty response from Gemini should raise ModelConnectionError."""
        from src.model_router import GeminiModel

        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.candidates = []
        mock_response.prompt_feedback = None

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai

        with pytest.raises(ModelConnectionError, match="empty"):
            model.generate("Hello!")

    def test_generate_invalid_api_key(self, gemini_settings):
        """Invalid API key should raise ConfigurationError."""
        from src.model_router import GeminiModel

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content.side_effect = \
            Exception("API_KEY_INVALID")

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai

        with pytest.raises(ConfigurationError, match="API key"):
            model.generate("Hello!")


# ============================================================
# GeminiModel Async Tests (mocked)
# ============================================================


class TestGeminiModelAsync:
    def test_async_generate(self, gemini_settings):
        """Async generate should return a ModelResponse."""
        from src.model_router import GeminiModel

        mock_response = MagicMock()
        mock_response.text = "Async Gemini response"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.candidates[0].content.parts[0].text = "Async Gemini response"
        mock_response.candidates[0].finish_reason = 1
        mock_response.prompt_feedback = None

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content_async = AsyncMock(
            return_value=mock_response
        )

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai

        result = asyncio.run(model.async_generate("Hello!"))
        assert isinstance(result, ModelResponse)
        assert result.text == "Async Gemini response"
        assert result.provider == PROVIDER_GEMINI

    def test_async_generate_with_context(self, gemini_settings):
        """Async generate with context should use chat mode."""
        from src.model_router import GeminiModel

        mock_chat = AsyncMock()
        mock_chat.send_message_async.return_value.text = "Async Gemini response"
        mock_chat.send_message_async.return_value.candidates = [MagicMock()]
        mock_chat.send_message_async.return_value.candidates[0].content.parts = [MagicMock()]
        mock_chat.send_message_async.return_value.candidates[0].content.parts[0].text = "Async Gemini response"
        mock_chat.send_message_async.return_value.candidates[0].finish_reason = 1
        mock_chat.send_message_async.return_value.prompt_feedback = None

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.start_chat.return_value = mock_chat

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai

        context = [{"role": "user", "content": "Previous"}]
        result = asyncio.run(model.async_generate("Hello!", context=context))
        assert isinstance(result, ModelResponse)
        assert result.text == "Async Gemini response"


# ============================================================
# GeminiModel Streaming Tests (mocked)
# ============================================================


class TestGeminiModelStream:
    def test_generate_stream(self, gemini_settings):
        """Stream should yield tokens from Gemini."""
        from src.model_router import GeminiModel

        # Mock streaming chunks
        chunk1 = MagicMock()
        chunk1.text = "Hello "
        chunk2 = MagicMock()
        chunk2.text = "from "
        chunk3 = MagicMock()
        chunk3.text = "Gemini!"
        mock_stream_response = [chunk1, chunk2, chunk3]

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_stream_response

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai

        async def collect():
            tokens = []
            async for token in model.generate_stream("Hello!"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) == 3
        assert tokens[0] == "Hello "
        assert tokens[1] == "from "
        assert tokens[2] == "Gemini!"

    def test_generate_stream_empty_chunks_skipped(self, gemini_settings):
        """Empty chunks should be skipped during streaming."""
        from src.model_router import GeminiModel

        chunk1 = MagicMock()
        chunk1.text = "Hello"
        chunk2 = MagicMock()
        chunk2.text = ""  # Empty chunk
        chunk3 = MagicMock()
        chunk3.text = " World"

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content.return_value = [chunk1, chunk2, chunk3]

        model = GeminiModel(gemini_settings)
        model._genai = mock_genai

        async def collect():
            tokens = []
            async for token in model.generate_stream("Hello!"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(collect())
        assert len(tokens) == 2  # Empty chunk skipped
        assert "".join(tokens) == "Hello World"


# ============================================================
# ModelRouter Mapping Tests
# ============================================================


class TestModelRouterMapping:
    def test_gemini_in_provider_map(self):
        """Gemini should be in ModelRouter's provider map."""
        assert PROVIDER_GEMINI in ModelRouter._PROVIDER_MAP

    def test_gemini_model_can_be_created(self, gemini_settings):
        """ModelRouter should create a GeminiModel when gemini is selected."""
        router = ModelRouter(gemini_settings)
        assert router.model is not None
        assert "Gemini" in type(router.model).__name__

    def test_gemini_generate_mocked(self, gemini_settings):
        """ModelRouter.generate should work with Gemini (mocked)."""
        from src.model_router import GeminiModel

        mock_response = MagicMock()
        mock_response.text = "Router Gemini response"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.candidates[0].content.parts[0].text = "Router Gemini response"
        mock_response.candidates[0].finish_reason = 1
        mock_response.prompt_feedback = None

        router = ModelRouter(gemini_settings)
        # Inject mock into the model
        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content.return_value = mock_response
        router.model._genai = mock_genai

        result = router.generate("Hello!")
        assert isinstance(result, ModelResponse)
        assert result.provider == PROVIDER_GEMINI

    def test_gemini_generate_async_mocked(self, gemini_settings):
        """ModelRouter.generate_async should work with Gemini (mocked)."""
        router = ModelRouter(gemini_settings)

        mock_response = MagicMock()
        mock_response.text = "Async Router Gemini"
        mock_response.candidates = [MagicMock()]
        mock_response.candidates[0].content.parts = [MagicMock()]
        mock_response.candidates[0].content.parts[0].text = "Async Router Gemini"
        mock_response.candidates[0].finish_reason = 1
        mock_response.prompt_feedback = None

        mock_genai = MagicMock()
        mock_genai.GenerativeModel.return_value.generate_content_async = AsyncMock(
            return_value=mock_response
        )
        router.model._genai = mock_genai

        result = asyncio.run(router.generate_async("Hello!"))
        assert isinstance(result, ModelResponse)
        assert result.provider == PROVIDER_GEMINI
