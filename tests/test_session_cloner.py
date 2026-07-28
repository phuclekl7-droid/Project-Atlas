"""
Unit tests for Session Cloner.

Tests:
- clone_session with valid session (mocked Memory)
- clone_session with non-existent session
- clone_session with empty session (no messages)
- clone_session with messages that have provider
- clone_session when memory raises error
- get_clone_name_suggestion
- clone session name format "[Copy] OriginalName"
"""

from unittest.mock import MagicMock, patch

import pytest

from handlers.session_cloner import clone_session, get_clone_name_suggestion


class MockMessage:
    """Minimal mock for a message object."""
    def __init__(self, role="user", content="Hello", provider=None):
        self.role = role
        self.content = content
        self.provider = provider


class TestCloneSession:
    def test_clone_successful(self):
        """Clone a session with messages should copy all messages."""
        mock_memory = MagicMock()

        # Mock source session
        mock_session = MagicMock()
        mock_session.name = "My Chat Session"
        mock_session.id = "src_123"
        mock_memory.get_session.return_value = mock_session

        # Mock new session creation
        mock_memory.create_session.return_value = "new_456"

        # Mock source messages
        mock_messages = [
            MockMessage(role="user", content="Hello"),
            MockMessage(role="assistant", content="Hi there!"),
            MockMessage(role="user", content="How are you?"),
        ]
        mock_memory.get_messages.return_value = mock_messages

        # Execute
        new_id = clone_session(mock_memory, "src_123")

        assert new_id == "new_456"
        mock_memory.create_session.assert_called_once_with(name="[Copy] My Chat Session")
        assert mock_memory.add_message.call_count == 3
        assert mock_memory.get_messages.call_count >= 1

    def test_clone_with_custom_name(self):
        """Custom new_name should be used instead of generated."""
        mock_memory = MagicMock()
        mock_session = MagicMock()
        mock_session.name = "Original"
        mock_memory.get_session.return_value = mock_session
        mock_memory.create_session.return_value = "new_789"
        mock_memory.get_messages.return_value = []
        mock_memory.add_message.return_value = "msg_1"

        new_id = clone_session(mock_memory, "src_123", new_name="Custom Clone")
        mock_memory.create_session.assert_called_once_with(name="Custom Clone")

    def test_clone_non_existent_session(self):
        """Non-existent session should return None."""
        mock_memory = MagicMock()
        mock_memory.get_session.return_value = None

        new_id = clone_session(mock_memory, "nonexistent")
        assert new_id is None

    def test_clone_with_provider(self):
        """Messages with provider should pass it to add_message."""
        mock_memory = MagicMock()
        mock_session = MagicMock()
        mock_session.name = "Test"
        mock_memory.get_session.return_value = mock_session
        mock_memory.create_session.return_value = "new_001"

        msg_with_provider = MockMessage(role="assistant", content="42", provider="openai")
        mock_memory.get_messages.return_value = [msg_with_provider]
        mock_memory.add_message.return_value = "msg_001"

        new_id = clone_session(mock_memory, "src_123")
        assert new_id == "new_001"
        # Check that add_message was called with provider
        call_kwargs = mock_memory.add_message.call_args[1]
        assert call_kwargs.get("provider") == "openai"

    def test_clone_empty_session(self):
        """Empty session (no messages) should still create a new session."""
        mock_memory = MagicMock()
        mock_session = MagicMock()
        mock_session.name = "Empty Chat"
        mock_memory.get_session.return_value = mock_session
        mock_memory.create_session.return_value = "new_empty"
        mock_memory.get_messages.return_value = []

        new_id = clone_session(mock_memory, "src_empty")
        assert new_id == "new_empty"
        assert mock_memory.add_message.call_count == 0  # No messages to copy

    def test_clone_memory_error(self):
        """If memory raises an exception, should return None."""
        mock_memory = MagicMock()
        mock_memory.get_session.side_effect = RuntimeError("DB locked")

        new_id = clone_session(mock_memory, "src_123")
        assert new_id is None

    def test_clone_none_memory(self):
        """None memory should return None."""
        new_id = clone_session(None, "src_123")
        assert new_id is None

    def test_clone_empty_session_id(self):
        """Empty session_id should return None."""
        mock_memory = MagicMock()
        new_id = clone_session(mock_memory, "")
        assert new_id is None

    def test_clone_skips_bad_messages(self):
        """If add_message fails for some messages, should continue."""
        mock_memory = MagicMock()
        mock_session = MagicMock()
        mock_session.name = "Partial"
        mock_memory.get_session.return_value = mock_session
        mock_memory.create_session.return_value = "new_partial"

        messages = [
            MockMessage(role="user", content="Keep me"),
            MockMessage(role="assistant", content="Troublemaker"),
        ]
        mock_memory.get_messages.return_value = messages

        # Second message causes error
        def mock_add(session, role, content, **kwargs):
            if "Troublemaker" in content:
                raise ValueError("Bad message")
            return "msg_ok"

        mock_memory.add_message.side_effect = mock_add

        new_id = clone_session(mock_memory, "src_partial")
        assert new_id == "new_partial"  # Should still return the new session ID


class TestGetCloneNameSuggestion:
    def test_with_valid_session(self):
        mock_memory = MagicMock()
        mock_session = MagicMock()
        mock_session.name = "My Chat"
        mock_memory.get_session.return_value = mock_session

        name = get_clone_name_suggestion(mock_memory, "src_123")
        assert name == "[Copy] My Chat"

    def test_with_none_session(self):
        mock_memory = MagicMock()
        mock_memory.get_session.return_value = None

        name = get_clone_name_suggestion(mock_memory, "src_123")
        assert name == "[Copy] Session"

    def test_with_session_no_name(self):
        mock_memory = MagicMock()
        mock_session = MagicMock()
        mock_session.name = ""
        mock_memory.get_session.return_value = mock_session

        name = get_clone_name_suggestion(mock_memory, "src_123")
        assert "Untitled" in name or "[Copy]" in name

    def test_with_error(self):
        mock_memory = MagicMock()
        mock_memory.get_session.side_effect = RuntimeError("fail")

        name = get_clone_name_suggestion(mock_memory, "src_123")
        assert name == "[Copy] Session"
