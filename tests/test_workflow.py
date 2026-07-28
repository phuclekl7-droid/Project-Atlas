"""
Unit tests for the Workflow module.

Tests:
- WorkflowResult dataclass
- Workflow initialization
- Full workflow process (Memory → Plugin → Model Router → Memory)
- Plugin routing (calculator input → plugin, not LLM)
- Error handling (empty input, connection errors)
- Stats tracking
"""

import pytest

from src.core import AssistantError, ConfigurationError, ModelConnectionError
from src.memory import Memory
from src.model_router import ModelRouter, ModelResponse
from src.plugin import PluginLoader, PluginResult
from src.settings import Settings, PROVIDER_MOCK
from src.workflow import Workflow, WorkflowResult


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def memory(tmp_path):
    """Create a temporary Memory instance."""
    db_path = tmp_path / "test_workflow.db"
    mem = Memory(str(db_path))
    yield mem
    mem.close()


@pytest.fixture
def settings():
    """Default Mock settings."""
    return Settings(model_provider=PROVIDER_MOCK)


@pytest.fixture
def model_router(settings):
    """Create a ModelRouter with Mock provider."""
    return ModelRouter(settings)


@pytest.fixture
def plugin_loader():
    """Create a PluginLoader and discover plugins."""
    loader = PluginLoader(plugin_package="src.plugins")
    loader.discover()
    return loader


@pytest.fixture
def workflow(memory, model_router, plugin_loader):
    """Create a Workflow with all dependencies."""
    return Workflow(
        memory=memory,
        model_router=model_router,
        plugin_loader=plugin_loader,
        max_context_messages=5,
    )


@pytest.fixture
def workflow_no_plugins(memory, model_router):
    """Create a Workflow without plugins."""
    return Workflow(
        memory=memory,
        model_router=model_router,
        plugin_loader=None,
        max_context_messages=5,
    )


# ============================================================
# WorkflowResult Tests
# ============================================================


class TestWorkflowResult:
    def test_llm_result(self):
        """An LLM-based result should show response text."""
        resp = ModelResponse(text="Hello!", model_name="m", provider="p")
        result = WorkflowResult(
            input="Hi",
            response=resp,
            source="llm",
            latency_ms=300.0,
            session_id="abc",
        )
        assert result.source == "llm"
        assert result.output_text == "Hello!"
        assert result.success is True
        assert result.response is not None
        assert result.plugin_result is None

    def test_plugin_result(self):
        """A plugin-based result should show plugin output."""
        plugin_res = PluginResult(success=True, output="42", data=42)
        result = WorkflowResult(
            input="2 + 3",
            plugin_result=plugin_res,
            source="plugin",
            latency_ms=50.0,
            session_id="abc",
        )
        assert result.source == "plugin"
        assert result.output_text == "42"
        assert result.success is True
        assert result.plugin_result is not None

    def test_repr(self):
        """__repr__ should show source and latency."""
        resp = ModelResponse(text="Hello world", model_name="m", provider="p")
        result = WorkflowResult(input="Hi", response=resp, latency_ms=300.0, session_id="a")
        r = repr(result)
        assert "llm" in r
        assert "300" in r


# ============================================================
# Workflow Initialization
# ============================================================


class TestWorkflowInit:
    def test_init_with_all_deps(self, workflow):
        """Workflow should initialize with all dependencies."""
        assert workflow.memory is not None
        assert workflow.model_router is not None
        assert workflow.plugin_loader is not None
        assert workflow.max_context_messages == 5
        assert workflow.total_processed == 0

    def test_init_without_plugins(self, workflow_no_plugins):
        """Workflow should work without plugins."""
        assert workflow_no_plugins.plugin_loader is None
        assert workflow_no_plugins.total_processed == 0

    def test_repr(self, workflow):
        """__repr__ should show stats."""
        r = repr(workflow)
        assert "Workflow" in r
        assert "0" in r  # processed = 0


# ============================================================
# Full Workflow Processing
# ============================================================


class TestWorkflowProcess:
    def test_process_llm_greeting(self, workflow, memory):
        """A greeting should route to LLM and return a response."""
        session_id = memory.create_session()
        result = workflow.process("Hello!", session_id=session_id)

        assert result.source == "llm"
        assert result.response is not None
        assert result.output_text != ""
        assert result.latency_ms >= 0
        assert result.session_id == session_id

    def test_process_llm_saves_to_memory(self, workflow, memory):
        """LLM responses should be saved to memory."""
        session_id = memory.create_session()
        before = memory.count_messages(session_id)
        workflow.process("Hello!", session_id=session_id)
        after = memory.count_messages(session_id)
        # Should have added user message + assistant response
        assert after == before + 2

    def test_process_plugin_calculator(self, workflow, memory):
        """A calculator input should route to plugin, not LLM."""
        session_id = memory.create_session()
        result = workflow.process("2 + 3", session_id=session_id)

        assert result.source == "plugin"
        assert result.plugin_result is not None
        assert result.plugin_result.success is True
        assert "5" in result.plugin_result.output
        assert result.latency_ms >= 0

    def test_process_plugin_saves_to_memory(self, workflow, memory):
        """Plugin outputs should be saved to memory as assistant messages."""
        session_id = memory.create_session()
        before = memory.count_messages(session_id)
        workflow.process("2 + 3", session_id=session_id)
        after = memory.count_messages(session_id)
        assert after == before + 2

    def test_process_multiple_steps_accumulates_context(self, workflow, memory):
        """Multiple messages should accumulate in context."""
        session_id = memory.create_session()
        workflow.process("Hello!", session_id=session_id)
        workflow.process("How are you?", session_id=session_id)
        workflow.process("What is 10 * 5?", session_id=session_id)

        messages = memory.get_messages(session_id)
        assert len(messages) == 6  # 3 user + 3 assistant
        assert messages[0].content == "Hello!"
        assert messages[2].content == "How are you?"

    def test_process_empty_input_raises(self, workflow, memory):
        """Empty input should raise AssistantError."""
        session_id = memory.create_session()
        with pytest.raises(AssistantError, match="cannot be empty"):
            workflow.process("", session_id=session_id)
        with pytest.raises(AssistantError, match="cannot be empty"):
            workflow.process("   ", session_id=session_id)


# ============================================================
# Workflow Without Plugins
# ============================================================


class TestWorkflowNoPlugins:
    def test_process_llm_only(self, workflow_no_plugins, memory):
        """Without plugins, all inputs go to LLM."""
        session_id = memory.create_session()
        result = workflow_no_plugins.process("2 + 3", session_id=session_id)
        # Even calculator input goes to LLM when no plugins
        assert result.source == "llm"

    def test_stats_no_plugin_calls(self, workflow_no_plugins, memory):
        """Without plugins, plugin call count should be 0."""
        session_id = memory.create_session()
        workflow_no_plugins.process("Hello!", session_id=session_id)
        stats = workflow_no_plugins.get_stats()
        assert stats["total_plugin_calls"] == 0


# ============================================================
# Stats Tracking
# ============================================================


class TestWorkflowStats:
    def test_stats_after_llm_calls(self, workflow, memory):
        """Stats should track LLM calls correctly."""
        session_id = memory.create_session()
        workflow.process("Hello!", session_id=session_id)
        workflow.process("How are you?", session_id=session_id)

        stats = workflow.get_stats()
        assert stats["total_processed"] == 2
        assert stats["total_llm_calls"] == 2
        assert stats["total_plugin_calls"] == 0

    def test_stats_after_plugin_calls(self, workflow, memory):
        """Stats should track plugin calls correctly."""
        session_id = memory.create_session()
        workflow.process("2 + 3", session_id=session_id)
        workflow.process("10 * 5", session_id=session_id)

        stats = workflow.get_stats()
        assert stats["total_processed"] == 2
        assert stats["total_llm_calls"] == 0
        assert stats["total_plugin_calls"] == 2

    def test_stats_mixed_calls(self, workflow, memory):
        """Stats should track mixed LLM and plugin calls."""
        session_id = memory.create_session()
        workflow.process("Hello!", session_id=session_id)  # LLM
        workflow.process("2 + 3", session_id=session_id)   # Plugin
        workflow.process("What is AI?", session_id=session_id)  # LLM

        stats = workflow.get_stats()
        assert stats["total_processed"] == 3
        assert stats["total_llm_calls"] == 2
        assert stats["total_plugin_calls"] == 1


# ============================================================
# Async Workflow Processing (process_async)
# ============================================================


class TestWorkflowProcessAsync:
    """Tests for the async process_async() method."""

    async def test_process_async_llm_greeting(self, workflow, memory):
        """A greeting should route to LLM via async path."""
        session_id = memory.create_session()
        result = await workflow.process_async("Hello!", session_id=session_id)

        assert result.source == "llm"
        assert result.response is not None
        assert result.output_text != ""
        assert result.latency_ms >= 0
        assert result.session_id == session_id

    async def test_process_async_saves_to_memory(self, workflow, memory):
        """Async responses should be saved to memory."""
        session_id = memory.create_session()
        before = memory.count_messages(session_id)
        await workflow.process_async("Hello!", session_id=session_id)
        after = memory.count_messages(session_id)
        assert after == before + 2

    async def test_process_async_plugin_calculator(self, workflow, memory):
        """A calculator input via async path should route to plugin."""
        session_id = memory.create_session()
        result = await workflow.process_async("2 + 3", session_id=session_id)

        assert result.source == "plugin"
        assert result.plugin_result is not None
        assert result.plugin_result.success is True
        assert "5" in result.plugin_result.output

    async def test_process_async_empty_input_raises(self, workflow, memory):
        """Empty input via async should raise AssistantError."""
        session_id = memory.create_session()
        with pytest.raises(AssistantError, match="cannot be empty"):
            await workflow.process_async("", session_id=session_id)

    async def test_process_async_stats_tracking(self, workflow, memory):
        """Async calls should update stats correctly."""
        session_id = memory.create_session()
        await workflow.process_async("Hello!", session_id=session_id)
        await workflow.process_async("2 + 3", session_id=session_id)

        stats = workflow.get_stats()
        assert stats["total_processed"] == 2
        assert stats["total_llm_calls"] == 1
        assert stats["total_plugin_calls"] == 1


# ============================================================
# Streaming (process_stream)
# ============================================================


class TestWorkflowProcessStream:
    """Tests for the streaming process_stream() method."""

    async def test_process_stream_llm(self, workflow, memory):
        """Streaming should yield tokens from the LLM."""
        session_id = memory.create_session()
        tokens = []
        async for token in workflow.process_stream("Hello!", session_id=session_id):
            tokens.append(token)

        full_text = "".join(tokens)
        assert len(full_text) > 0
        assert len(tokens) > 0  # Should have yielded multiple tokens (word-by-word for Mock)

    async def test_process_stream_saves_to_memory(self, workflow, memory):
        """Streaming responses should be saved to memory after completion."""
        session_id = memory.create_session()
        before = memory.count_messages(session_id)

        async for _ in workflow.process_stream("Hello!", session_id=session_id):
            pass

        after = memory.count_messages(session_id)
        assert after == before + 2

    async def test_process_stream_plugin(self, workflow, memory):
        """Calculator input via streaming should yield plugin output as single token."""
        session_id = memory.create_session()
        tokens = []
        async for token in workflow.process_stream("2 + 3", session_id=session_id):
            tokens.append(token)

        full_text = "".join(tokens)
        assert "5" in full_text

    async def test_process_stream_empty_input_raises(self, workflow, memory):
        """Empty input via stream should raise AssistantError."""
        session_id = memory.create_session()
        with pytest.raises(AssistantError, match="cannot be empty"):
            async for _ in workflow.process_stream("", session_id=session_id):
                pass

    async def test_process_stream_stats_tracking(self, workflow, memory):
        """Streaming should update stats correctly."""
        session_id = memory.create_session()
        async for _ in workflow.process_stream("Hello!", session_id=session_id):
            pass
        async for _ in workflow.process_stream("2 + 3", session_id=session_id):
            pass

        stats = workflow.get_stats()
        assert stats["total_processed"] == 2
        assert stats["total_llm_calls"] == 1
        assert stats["total_plugin_calls"] == 1


# ============================================================
# Context Limit
# ============================================================


class TestWorkflowContext:
    def test_context_respects_limit(self, workflow, memory):
        """Workflow should respect max_context_messages."""
        session_id = memory.create_session()
        # Send 6 messages (3 exchanges)
        workflow.process("A", session_id=session_id)
        workflow.process("B", session_id=session_id)
        workflow.process("C", session_id=session_id)

        # Context should include only the most recent messages
        context = memory.get_context(session_id, limit=workflow.max_context_messages)
        assert len(context) <= workflow.max_context_messages
