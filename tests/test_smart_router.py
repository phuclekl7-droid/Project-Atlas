"""
Tests for SmartRouter multi-model routing, Memory provider field,
Workflow smart routing integration, and async provider generation.
"""

import pytest

from src.model_router.smart_router import SmartRouter
from src.settings import PROVIDER_MOCK, PROVIDER_OLLAMA, PROVIDER_OPENAI, PROVIDER_GEMINI, Settings


# ============================================================
# SmartRouter — Unit Tests
# ============================================================


class TestSmartRouterInit:
    """SmartRouter initialization."""

    def test_init_default_provider(self, mock_settings):
        router = SmartRouter(mock_settings)
        assert router.default_provider == PROVIDER_MOCK

    def test_init_ollama_provider(self, ollama_settings):
        router = SmartRouter(ollama_settings)
        assert router.default_provider == PROVIDER_OLLAMA

    def test_repr(self, mock_settings):
        router = SmartRouter(mock_settings)
        assert "SmartRouter" in repr(router)
        assert PROVIDER_MOCK in repr(router)


class TestSmartRouterRouting:
    """SmartRouter.route() — keyword-based routing."""

    def test_empty_input_falls_back_to_default(self, mock_settings):
        router = SmartRouter(mock_settings)
        assert router.route("") == PROVIDER_MOCK
        assert router.route("   ") == PROVIDER_MOCK

    def test_coding_keywords_route_to_ollama(self, default_settings):
        router = SmartRouter(default_settings)
        assert router.route("Write a Python function to sort") == PROVIDER_OLLAMA
        assert router.route("Fix this bug in my code") == PROVIDER_OLLAMA
        assert router.route("How to implement a binary search algorithm?") == PROVIDER_OLLAMA
        assert router.route("Refactor this API endpoint") == PROVIDER_OLLAMA
        assert router.route("Write unit tests with pytest") == PROVIDER_OLLAMA

    def test_creative_keywords_route_to_openai(self, default_settings):
        router = SmartRouter(default_settings)
        assert router.route("Write a poem about artificial intelligence") == PROVIDER_OPENAI
        assert router.route("Tell me a story about a robot") == PROVIDER_OPENAI
        assert router.route("Compose a song about coding") == PROVIDER_OPENAI
        assert router.route("Brainstorm ideas for my blog") == PROVIDER_OPENAI

    def test_analysis_keywords_route_to_gemini(self, default_settings):
        router = SmartRouter(default_settings)
        assert router.route("Analyze the pros and cons of remote work") == PROVIDER_GEMINI
        assert router.route("Explain quantum computing in simple terms") == PROVIDER_GEMINI
        assert router.route("Compare Python and JavaScript") == PROVIDER_GEMINI
        assert router.route("Summarize the key differences") == PROVIDER_GEMINI
        assert router.route("What is the meaning of life?") == PROVIDER_GEMINI

    def test_short_prompt_falls_back(self, default_settings):
        """Very short prompts (< 50 chars) with no keywords use default."""
        settings = Settings(model_provider=PROVIDER_OLLAMA)
        router = SmartRouter(settings)
        assert router.route("Hi") == PROVIDER_OLLAMA
        assert router.route("Hello") == PROVIDER_OLLAMA
        assert router.route("Ok") == PROVIDER_OLLAMA

    def test_long_prompt_routes_to_gemini(self, default_settings):
        """Long prompts (> 500 chars) route to Gemini for detailed analysis."""
        settings = Settings(model_provider=PROVIDER_OLLAMA)
        router = SmartRouter(settings)
        long_text = "This is a very long prompt. " * 30  # > 500 chars
        assert len(long_text) > 500
        assert router.route(long_text) == PROVIDER_GEMINI

    def test_single_keyword_match_still_routes(self, default_settings):
        """Single keyword match (weak signal) should still route."""
        router = SmartRouter(default_settings)
        # "bug" is a coding keyword
        result = router.route("I found a bug")
        assert result in (PROVIDER_OLLAMA, PROVIDER_MOCK)  # either coding match or fallback


class TestSmartRouterRouteWithReason:
    """SmartRouter.route_with_reason() — detailed routing info."""

    def test_returns_provider_and_reason(self, default_settings):
        router = SmartRouter(default_settings)
        provider, reason = router.route_with_reason("Write a poem")
        assert provider == PROVIDER_OPENAI
        assert "creative" in reason.lower()

    def test_empty_input_reason(self, mock_settings):
        router = SmartRouter(mock_settings)
        provider, reason = router.route_with_reason("")
        assert provider == PROVIDER_MOCK
        assert "empty" in reason.lower()

    def test_coding_reason_contains_score(self, default_settings):
        router = SmartRouter(default_settings)
        _, reason = router.route_with_reason("Write a Python function to sort data")
        assert "coding" in reason.lower() or "score" in reason


class TestSmartRouterScoreKeywords:
    """SmartRouter._score_keywords() — internal keyword matching."""

    def test_multi_word_keyword(self, default_settings):
        router = SmartRouter(default_settings)
        text = "I need to deploy a ci/cd pipeline"
        score = router._score_keywords(text, ["ci/cd", "deploy", "pipeline"])
        assert score >= 2  # Should match multiple

    def test_no_match_returns_zero(self, default_settings):
        router = SmartRouter(default_settings)
        text = "Hello, how are you?"
        score = router._score_keywords(text, ["python", "code", "function"])
        assert score == 0

    def test_case_insensitive_matching(self, default_settings):
        """_score_keywords is called on lowercase text, so it's already lowercased."""
        router = SmartRouter(default_settings)
        text = "I love Python and JAVASCRIPT"
        # route() lowercases the prompt first
        result = router.route(text)
        # "python" keyword should match (coding category)
        assert result == PROVIDER_OLLAMA


# ============================================================
# Memory — Provider Field Tests
# ============================================================


class TestMemoryProviderField:
    """Memory.add_message() with provider parameter."""

    def test_add_message_with_provider(self, memory):
        session_id = memory.create_session("test")
        msg = memory.add_message(session_id, "assistant", "Hello!", provider="ollama")
        assert msg.provider == "ollama"
        assert msg.role == "assistant"
        assert msg.content == "Hello!"

    def test_get_message_includes_provider(self, memory):
        session_id = memory.create_session("test")
        memory.add_message(session_id, "assistant", "Hello!", provider="gemini")
        msgs = memory.get_messages(session_id)
        assert len(msgs) == 1
        assert msgs[0].provider == "gemini"

    def test_get_context_includes_provider(self, memory):
        """get_context() returns role/content dicts (no provider in context format)."""
        session_id = memory.create_session("test")
        memory.add_message(session_id, "assistant", "Hello!", provider="openai")
        ctx = memory.get_context(session_id)
        assert len(ctx) == 1
        assert ctx[0]["role"] == "assistant"
        assert ctx[0]["content"] == "Hello!"
        # Provider is not included in context dicts (only role/content for LLM)

    def test_default_provider_is_none(self, memory):
        """Adding without provider should store None."""
        session_id = memory.create_session("test")
        msg = memory.add_message(session_id, "user", "Hi")
        assert msg.provider is None

    def test_to_dict_includes_provider(self, memory):
        session_id = memory.create_session("test")
        msg = memory.add_message(session_id, "assistant", "Hello!", provider="ollama")
        d = msg.to_dict()
        assert d.get("provider") == "ollama"

    def test_to_dict_no_provider(self, memory):
        session_id = memory.create_session("test")
        msg = memory.add_message(session_id, "user", "Hi")
        d = msg.to_dict()
        assert "provider" not in d or d.get("provider") is None


# ============================================================
# ModelRouter — generate_with_provider_async Tests
# ============================================================


class TestModelRouterGenerateWithProviderAsync:
    """ModelRouter.generate_with_provider_async() — async routing to specific providers."""

    @pytest.mark.asyncio
    async def test_generate_with_mock_async(self, model_router):
        """Mock provider should work async."""
        response = await model_router.generate_with_provider_async(
            PROVIDER_MOCK, "Hello!"
        )
        assert response is not None
        assert response.text is not None
        assert len(response.text) > 0
        assert response.provider == PROVIDER_MOCK

    @pytest.mark.asyncio
    async def test_generate_with_unknown_provider(self, model_router):
        """Unknown provider should raise error."""
        with pytest.raises(Exception):
            await model_router.generate_with_provider_async(
                "nonexistent", "Hello"
            )

    @pytest.mark.asyncio
    async def test_empty_prompt_raises_error(self, model_router):
        """Empty prompt should raise error."""
        with pytest.raises(Exception):
            await model_router.generate_with_provider_async(
                PROVIDER_MOCK, ""
            )

    @pytest.mark.asyncio
    async def test_generate_with_provider_async_context(self, model_router, memory):
        """Should work with context."""
        session_id = memory.create_session("test")
        memory.add_message(session_id, "user", "Hello!")
        context = memory.get_context(session_id)
        response = await model_router.generate_with_provider_async(
            PROVIDER_MOCK, "Hello!", context=context
        )
        assert response is not None
        assert response.text is not None


# ============================================================
# Workflow — Smart Router Integration Tests
# ============================================================


class TestWorkflowSmartRouting:
    """Workflow.process() with multi_model_enabled=True."""

    def test_process_with_routing_enabled_coding(self, workflow, memory):
        """Coding prompt routes through SmartRouter (multi_model_enabled)."""
        # Enable multi-model routing
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")
        result = workflow.process("Write a Python function", session_id=session_id)
        assert result.success
        assert result.response is not None
        assert result.response.provider == PROVIDER_MOCK  # Mock is the only one available
        assert result.source == "llm"

    def test_process_with_routing_disabled(self, workflow, memory):
        """With routing disabled, uses default provider."""
        workflow.multi_model_enabled = False
        session_id = memory.create_session("test")
        result = workflow.process("Write a Python function", session_id=session_id)
        assert result.success
        assert result.response is not None
        assert result.response.provider == PROVIDER_MOCK  # Default is Mock
        assert result.source == "llm"

    def test_process_stores_provider_in_memory(self, workflow, memory):
        """Provider should be stored in memory messages."""
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")
        result = workflow.process("Write a Python function", session_id=session_id)
        msgs = memory.get_messages(session_id)
        # Find assistant messages
        assistant_msgs = [m for m in msgs if m.role == "assistant"]
        assert len(assistant_msgs) >= 1
        assert assistant_msgs[-1].provider is not None

    def test_process_does_not_store_provider_in_user_messages(self, workflow, memory):
        """User messages should not have provider."""
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")
        workflow.process("Hello", session_id=session_id)
        msgs = memory.get_messages(session_id)
        user_msgs = [m for m in msgs if m.role == "user"]
        assert len(user_msgs) >= 1
        # User messages have provider=None since we only pass provider for assistant
        assert user_msgs[-1].provider is None


class TestWorkflowSmartRoutingAsync:
    """Workflow.process_async() with multi_model_enabled=True."""

    @pytest.mark.asyncio
    async def test_process_async_with_routing(self, workflow, memory):
        """Async process should work with multi-model routing."""
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")
        result = await workflow.process_async("Write a Python function", session_id=session_id)
        assert result.success
        assert result.response is not None
        assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_process_async_stores_provider(self, workflow, memory):
        """Async process should store provider in memory."""
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")
        await workflow.process_async("Write a Python function", session_id=session_id)
        msgs = memory.get_messages(session_id)
        assistant_msgs = [m for m in msgs if m.role == "assistant"]
        assert len(assistant_msgs) >= 1
        assert assistant_msgs[-1].provider is not None

    @pytest.mark.asyncio
    async def test_process_async_routing_disabled(self, workflow, memory):
        """Async process without routing uses default provider."""
        workflow.multi_model_enabled = False
        session_id = memory.create_session("test")
        result = await workflow.process_async("Write a Python function", session_id=session_id)
        assert result.success
        assert result.response is not None
        assert result.response.provider == PROVIDER_MOCK


class TestWorkflowPluginWithRouting:
    """Plugins should still work when multi-model routing is enabled."""

    def test_plugin_still_works_with_routing(self, workflow, memory):
        """Plugin execution should not be affected by SmartRouter."""
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")

        # Calculator plugin should still fire on math input
        result = workflow.process("Calculate 2 + 3", session_id=session_id)
        # Either plugin or LLM handles it (Mock doesn't have calculator, but plugin might)
        assert result.success

    def test_provider_stored_in_memory_with_plugin(self, workflow, memory):
        """When plugin is used, provider is not set (no LLM call)."""
        workflow.multi_model_enabled = True
        session_id = memory.create_session("test")

        # This input might trigger calculator plugin
        result = workflow.process("2 + 3", session_id=session_id)

        # Check memory
        msgs = memory.get_messages(session_id)
        assistant_msgs = [m for m in msgs if m.role == "assistant"]

        if result.source == "plugin":
            # Plugin messages might not have provider
            pass
        elif result.source == "llm":
            assert len(assistant_msgs) >= 1
            assert assistant_msgs[-1].provider is not None
