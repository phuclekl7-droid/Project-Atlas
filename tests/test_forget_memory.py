"""Tests for Forget Memory API (Feature 19) and /forget command."""

import os
import tempfile

import pytest

from src.memory import Memory
from src.workflow import Workflow, WorkflowResult


@pytest.fixture
def memory():
    """Create a temporary Memory instance."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    mem = Memory(db_path)
    yield mem
    mem.close()
    os.unlink(db_path)


@pytest.fixture
def session_id(memory):
    """Create a test session with messages."""
    sid = memory.create_session("Test Session")
    messages = [
        ("user", "Hello, my name is John"),
        ("assistant", "Hi John! How can I help you?"),
        ("user", "I live in New York"),
        ("assistant", "Great city! What do you need?"),
        ("user", "My email is john@example.com"),
        ("assistant", "Got it, I'll remember that."),
        ("user", "I'm learning Python"),
        ("assistant", "Python is awesome!"),
    ]
    for role, content in messages:
        memory.add_message(sid, role, content)
    return sid


class TestForgetMemoryByPattern:
    """Test the forget_messages_by_pattern method."""

    def test_forget_basic_pattern(self, memory, session_id):
        """Test deleting messages by content pattern."""
        deleted = memory.forget_messages_by_pattern(session_id, "John")
        assert deleted == 2  # "my name is John" and "john@example.com"
        remaining = memory.get_messages(session_id)
        assert len(remaining) == 8 - deleted  # 6 remain
        # Verify "John" no longer appears
        for m in remaining:
            assert "john" not in m.content.lower()

    def test_forget_case_insensitive(self, memory, session_id):
        """Test that pattern matching is case-insensitive."""
        deleted = memory.forget_messages_by_pattern(session_id, "john")
        assert deleted >= 2  # Both "John" mentions

    def test_forget_no_match(self, memory, session_id):
        """Test with pattern that doesn't exist."""
        deleted = memory.forget_messages_by_pattern(session_id, "nonexistent")
        assert deleted == 0
        remaining = memory.get_messages(session_id)
        assert len(remaining) == 8

    def test_forget_empty_pattern(self, memory, session_id):
        """Test with empty pattern."""
        deleted = memory.forget_messages_by_pattern(session_id, "")
        assert deleted == 0

    def test_forget_whitespace_pattern(self, memory, session_id):
        """Test with whitespace-only pattern."""
        deleted = memory.forget_messages_by_pattern(session_id, "   ")
        assert deleted == 0

    def test_forget_nonexistent_session(self, memory):
        """Test with a session that doesn't exist."""
        deleted = memory.forget_messages_by_pattern("nonexistent", "hello")
        assert deleted == 0

    def test_forget_after_deletion(self, memory, session_id):
        """Test session message count is updated after forget."""
        before_count = memory.get_session(session_id).message_count
        memory.forget_messages_by_pattern(session_id, "email")
        after_count = memory.get_session(session_id).message_count
        assert after_count == before_count - 1


class TestForgetCommandInWorkflow:
    """Test the /forget command integration in Workflow."""

    def test_forget_command_detection(self, mocker):
        """Test that /forget prefix triggers the handler."""
        mock_memory = mocker.MagicMock(spec=Memory)
        mock_memory.forget_messages_by_pattern.return_value = 2
        mock_router = mocker.MagicMock()
        mock_loader = mocker.MagicMock()

        workflow = Workflow(mock_memory, mock_router, mock_loader)
        result = workflow.process("/forget John", "test_session")

        assert result.success
        assert "xóa" in result.output_text.lower() or "deleted" in result.output_text.lower()
        mock_memory.forget_messages_by_pattern.assert_called_once_with("test_session", "John")

    def test_forget_command_no_pattern(self, mocker):
        """Test /forget without a pattern."""
        mock_memory = mocker.MagicMock(spec=Memory)
        mock_router = mocker.MagicMock()
        mock_loader = mocker.MagicMock()

        workflow = Workflow(mock_memory, mock_router, mock_loader)
        result = workflow.process("/forget", "test_session")

        assert result.success
        assert "cách" in result.output_text.lower()

    def test_forget_command_no_match(self, mocker):
        """Test /forget with pattern that doesn't match."""
        mock_memory = mocker.MagicMock(spec=Memory)
        mock_memory.forget_messages_by_pattern.return_value = 0
        mock_router = mocker.MagicMock()
        mock_loader = mocker.MagicMock()

        workflow = Workflow(mock_memory, mock_router, mock_loader)
        result = workflow.process("/forget nonexistent", "test_session")

        assert result.success
        assert "không tìm thấy" in result.output_text.lower() or "no" in result.output_text.lower()

    def test_forget_does_not_block_normal_input(self, mocker):
        """Test that normal input (not /forget) still goes to model."""
        mock_memory = mocker.MagicMock(spec=Memory)
        mock_memory.get_context.return_value = []
        mock_router = mocker.MagicMock()
        mock_router.generate.return_value.text = "Hello!"
        mock_router.generate.return_value.provider = "mock"
        mock_loader = mocker.MagicMock()

        workflow = Workflow(mock_memory, mock_router, mock_loader)
        result = workflow.process("What is Python?", "test_session")

        assert result.success
        assert result.source == "llm"
