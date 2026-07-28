""""
Integration tests for the full pipeline: Memory → Plugin → Workflow → ModelRouter.

Tests all three execution modes:
- Sync: workflow.process()
- Async: workflow.process_async()
- Streaming: workflow.process_stream()

Also tests error propagation, context accumulation, and cross-mode consistency.
"""

import asyncio

import pytest

from src.core import AssistantError, ConfigurationError, ModelConnectionError
from src.model_router import ModelResponse
from src.workflow import WorkflowResult


# ============================================================
# Fixtures — use shared fixtures from conftest.py
# (memory, model_router, plugin_loader, workflow, workflow_no_plugins)
# ============================================================


@pytest.fixture
def session_id(memory):
    """Create and return a fresh session ID."""
    return memory.create_session()


# ============================================================
# Full Sync Pipeline
# ============================================================


class TestFullSyncPipeline:
    """Test the complete sync pipeline: Memory → Plugin → Workflow → ModelRouter."""

    def test_greeting_flows_through_entire_pipeline(self, workflow, session_id):
        """A greeting should flow through Memory → Workflow → ModelRouter → Memory."""
        result = workflow.process("Hello!", session_id=session_id)

        # 1. ModelRouter returned a response
        assert result.source == "llm"
        assert isinstance(result.response, ModelResponse)
        assert "Xin chào" in result.output_text

        # 2. Memory was updated (user + assistant)
        messages = workflow.memory.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "Hello!"
        assert messages[1].role == "assistant"

        # 3. Stats were tracked
        assert workflow.total_processed == 1
        assert workflow.total_llm_calls == 1

    def test_plugin_intercepts_before_llm(self, workflow, session_id):
        """Calculator input should be intercepted by Plugin BEFORE reaching ModelRouter."""
        result = workflow.process("2 + 3", session_id=session_id)

        # Plugin handled it — no LLM call
        assert result.source == "plugin"
        assert result.plugin_result is not None
        assert result.plugin_result.success
        assert "5" in result.output_text
        assert result.response is None  # No model response

        # No LLM call was made
        assert workflow.total_llm_calls == 0
        assert workflow.total_plugin_calls == 1

    def test_plugin_then_llm_mixed(self, workflow, session_id):
        """Mixed plugin and LLM calls should both work in sequence."""
        # Plugin call
        r1 = workflow.process("2 + 3", session_id=session_id)
        assert r1.source == "plugin"

        # LLM call
        r2 = workflow.process("Hello!", session_id=session_id)
        assert r2.source == "llm"

        assert workflow.total_plugin_calls == 1
        assert workflow.total_llm_calls == 1
        assert workflow.total_processed == 2

    def test_full_pipeline_empty_input(self, workflow, session_id):
        """Empty input should raise error at the top of the pipeline."""
        with pytest.raises(AssistantError, match="cannot be empty"):
            workflow.process("", session_id=session_id)

        # Nothing was saved to memory
        assert workflow.total_processed == 0

    def test_full_pipeline_no_plugins(self, workflow_no_plugins, session_id):
        """Without plugins, ALL inputs go to LLM (even calculator)."""
        result = workflow_no_plugins.process("2 + 3", session_id=session_id)
        assert result.source == "llm"  # No plugin to intercept
        assert result.response is not None

    def test_full_pipeline_context_accumulates(self, workflow, session_id):
        """Messages should accumulate in memory across multiple calls."""
        workflow.process("First message", session_id=session_id)
        workflow.process("Second message", session_id=session_id)
        workflow.process("Third message", session_id=session_id)

        messages = workflow.memory.get_messages(session_id)
        assert len(messages) == 6  # 3 user + 3 assistant
        assert messages[0].content == "First message"
        assert messages[2].content == "Second message"
        assert messages[4].content == "Third message"

    def test_full_pipeline_context_injected(self, workflow, session_id):
        """Context should include previous messages and affect Mock response."""
        workflow.process("Hello!", session_id=session_id)
        # Send another message — Mock will see context includes the previous exchange
        result = workflow.process("How are you?", session_id=session_id)
        assert result.context_used > 0
        assert result.response is not None

    def test_full_pipeline_stats_accurate(self, workflow, session_id):
        """Pipeline stats should accurately reflect all operations."""
        workflow.process("2 + 3", session_id=session_id)    # Plugin
        workflow.process("Hello!", session_id=session_id)   # LLM
        workflow.process("10 * 5", session_id=session_id)   # Plugin
        workflow.process("What is AI?", session_id=session_id)  # LLM

        stats = workflow.get_stats()
        assert stats["total_processed"] == 4
        assert stats["total_llm_calls"] == 2
        assert stats["total_plugin_calls"] == 2
        assert stats["total_kb_lookups"] == 0  # No KB configured

    def test_full_pipeline_multiple_sessions_isolated(self, workflow, memory):
        """Different sessions should not share context."""
        s1 = memory.create_session()
        s2 = memory.create_session()

        workflow.process("Session 1 message", session_id=s1)
        workflow.process("Session 2 message", session_id=s2)

        msgs1 = workflow.memory.get_messages(s1)
        msgs2 = workflow.memory.get_messages(s2)

        assert len(msgs1) == 2
        assert msgs1[0].content == "Session 1 message"
        assert len(msgs2) == 2
        assert msgs2[0].content == "Session 2 message"


# ============================================================
# Full Async Pipeline
# ============================================================


class TestFullAsyncPipeline:
    """Test the complete async pipeline: Memory → Workflow.process_async() → ModelRouter."""

    def test_async_greeting(self, workflow, session_id):
        """Async greeting should flow through the entire pipeline."""

        async def run():
            return await workflow.process_async("Hello!", session_id=session_id)

        result = asyncio.run(run())
        assert result.source == "llm"
        assert isinstance(result.response, ModelResponse)
        assert "Xin chào" in result.output_text

    def test_async_plugin_intercepts(self, workflow, session_id):
        """Async pipeline should still route plugin calls to Plugin, not LLM."""

        async def run():
            return await workflow.process_async("2 + 3", session_id=session_id)

        result = asyncio.run(run())
        assert result.source == "plugin"
        assert "5" in result.output_text

    def test_async_saves_to_memory(self, workflow, session_id):
        """Async pipeline should save both user and assistant messages to memory."""

        async def run():
            return await workflow.process_async("Hello!", session_id=session_id)

        result = asyncio.run(run())
        messages = workflow.memory.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_async_empty_input(self, workflow, session_id):
        """Async pipeline should reject empty input."""

        async def run():
            with pytest.raises(AssistantError, match="cannot be empty"):
                await workflow.process_async("", session_id=session_id)

        asyncio.run(run())

    def test_async_and_sync_same_output(self, workflow, memory):
        """Sync and async pipelines should produce the same output for same input.
        Uses separate sessions to avoid context pollution affecting Mock output.
        """
        sync_sid = memory.create_session()
        async_sid = memory.create_session()

        async def run():
            sync_result = workflow.process("Help me!", session_id=sync_sid)
            async_result = await workflow.process_async("Help me!", session_id=async_sid)
            return sync_result, async_result

        sync, async_ = asyncio.run(run())
        assert sync.output_text == async_.output_text
        assert sync.source == async_.source

    def test_async_multiple_in_sequence(self, workflow, session_id):
        """Multiple async calls in sequence should all succeed."""

        async def run():
            r1 = await workflow.process_async("First", session_id=session_id)
            r2 = await workflow.process_async("Second", session_id=session_id)
            r3 = await workflow.process_async("Third", session_id=session_id)
            return r1, r2, r3

        r1, r2, r3 = asyncio.run(run())
        assert r1.success
        assert r2.success
        assert r3.success
        assert workflow.total_processed == 3


# ============================================================
# Full Streaming Pipeline
# ============================================================


class TestFullStreamingPipeline:
    """Test the complete streaming pipeline: Memory → Workflow.process_stream() → ModelRouter."""

    def test_streaming_llm_response(self, workflow, session_id):
        """Streaming pipeline should yield tokens from LLM."""

        async def run():
            tokens = []
            async for token in workflow.process_stream("Hello!", session_id=session_id):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(run())
        assert len(tokens) > 0
        assert any("Xin" in t for t in tokens)

    def test_streaming_plugin_response(self, workflow, session_id):
        """Streaming pipeline should yield plugin output as single token."""

        async def run():
            tokens = []
            async for token in workflow.process_stream("2 + 3", session_id=session_id):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(run())
        assert len(tokens) == 1
        assert "5" in tokens[0]

    def test_streaming_saves_to_memory(self, workflow, session_id):
        """Streaming pipeline should save complete response to memory after streaming."""

        async def run():
            async for _ in workflow.process_stream("Hello!", session_id=session_id):
                pass

        asyncio.run(run())
        messages = workflow.memory.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert len(messages[1].content) > 0

    def test_streaming_empty_input(self, workflow, session_id):
        """Streaming pipeline should reject empty input."""

        async def run():
            with pytest.raises(AssistantError, match="cannot be empty"):
                async for _ in workflow.process_stream("", session_id=session_id):
                    pass

        asyncio.run(run())

    def test_streaming_and_async_text_identical(self, workflow, memory):
        """Streaming and async should produce the same final text.
        Uses separate sessions to avoid context pollution affecting Mock output.
        """
        async_sid = memory.create_session()
        stream_sid = memory.create_session()

        async def run():
            async_result = await workflow.process_async("Hello!", session_id=async_sid)

            tokens = []
            async for token in workflow.process_stream("Hello!", session_id=stream_sid):
                tokens.append(token)
            streamed_text = "".join(tokens)

            return async_result.output_text, streamed_text

        async_text, streamed_text = asyncio.run(run())
        # Mock words have trailing spaces in streaming; rstrip for comparison
        assert streamed_text.rstrip() == async_text.rstrip()

    def test_streaming_multiple_sessions(self, workflow, memory):
        """Streaming pipeline should work with multiple sessions independently."""
        s1 = memory.create_session()
        s2 = memory.create_session()

        async def stream_session(sid, message):
            tokens = []
            async for token in workflow.process_stream(message, session_id=sid):
                tokens.append(token)
            return "".join(tokens)

        async def run():
            t1 = await stream_session(s1, "Hello!")
            t2 = await stream_session(s2, "How are you?")
            return t1, t2

        t1, t2 = asyncio.run(run())
        assert len(t1) > 0
        assert len(t2) > 0
        # Verify messages are in correct sessions
        assert workflow.memory.get_messages(s1)[0].content == "Hello!"
        assert workflow.memory.get_messages(s2)[0].content == "How are you?"


# ============================================================
# Cross-Mode Consistency
# ============================================================


class TestCrossModeConsistency:
    """Sync, async, and streaming modes should be consistent."""

    def test_sync_async_stream_same_session(self, workflow, session_id):
        """All three modes should work in the same session."""
        # Sync
        workflow.process("2 + 3", session_id=session_id)
        # Async
        asyncio.run(workflow.process_async("Hello!", session_id=session_id))
        # Streaming
        async def stream():
            async for _ in workflow.process_stream("What is AI?", session_id=session_id):
                pass
        asyncio.run(stream())

        messages = workflow.memory.get_messages(session_id)
        assert len(messages) == 6  # 3 user + 3 assistant

    def test_sync_async_stream_stats(self, workflow, session_id):
        """Stats should be consistent across all modes."""
        workflow.process("Hello!", session_id=session_id)           # sync LLM
        workflow.process("2 + 3", session_id=session_id)            # sync Plugin
        asyncio.run(workflow.process_async("Hi!", session_id=session_id))  # async LLM
        async def stream():
            async for _ in workflow.process_stream("10 * 5", session_id=session_id):
                pass
        asyncio.run(stream())  # stream Plugin

        stats = workflow.get_stats()
        assert stats["total_processed"] == 4
        assert stats["total_llm_calls"] == 2
        assert stats["total_plugin_calls"] == 2


# ============================================================
# Error Propagation
# ============================================================


class TestPipelineErrorPropagation:
    """Errors should propagate correctly through the entire pipeline."""

    def test_assistant_error_propagates(self, workflow, session_id):
        """AssistantError at the input level should propagate."""
        with pytest.raises(AssistantError, match="cannot be empty"):
            workflow.process("", session_id=session_id)

    def test_assistant_error_async_propagates(self, workflow, session_id):
        """AssistantError should propagate through async pipeline."""

        async def run():
            with pytest.raises(AssistantError, match="cannot be empty"):
                await workflow.process_async("", session_id=session_id)

        asyncio.run(run())

    def test_assistant_error_stream_propagates(self, workflow, session_id):
        """AssistantError should propagate through streaming pipeline."""

        async def run():
            with pytest.raises(AssistantError, match="cannot be empty"):
                async for _ in workflow.process_stream("", session_id=session_id):
                    pass

        asyncio.run(run())

    def test_workflow_continues_after_error(self, workflow, session_id):
        """Workflow should continue working after an error."""

        async def run():
            with pytest.raises(AssistantError):
                await workflow.process_async("", session_id=session_id)
            # Subsequent call should still work
            result = await workflow.process_async("Hello!", session_id=session_id)
            assert result.success
            assert workflow.total_processed == 1

        asyncio.run(run())
