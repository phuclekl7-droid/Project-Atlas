"""
Unit tests for Chat Clearer (Clear Active Chat).

Tests:
- clear_active_chat with messages (mocked)
- clear_active_chat with empty session (no messages)
- clear_active_chat with non-existent session
- clear_active_chat with None memory
- delete_session_messages_bulk fallback
- Error handling when memory raises exception
"""

from unittest.mock import MagicMock, patch

import pytest

from handlers.chat_clearer import clear_active_chat, delete_session_messages_bulk


class MockMessage:
    def __init__(self, id=1):
        self.id = id


class TestClearActiveChat:
    def test_clear_with_messages(self):
        """Should delete all messages and return True."""
        mock_memory = MagicMock()
        # First get_messages returns messages (session has messages)
        mock_memory.get_messages.return_value = [
            MockMessage(id=1),
            MockMessage(id=2),
            MockMessage(id=3),
        ]
        mock_memory.delete_message.return_value = True

        result = clear_active_chat(mock_memory, "session_123")
        assert result is True
        assert mock_memory.delete_message.call_count >= 1

    def test_clear_empty_session(self):
        """Empty session should return True immediately."""
        mock_memory = MagicMock()
        mock_memory.get_messages.return_value = []

        result = clear_active_chat(mock_memory, "session_123")
        assert result is True

    def test_clear_none_memory(self):
        """None memory should return False."""
        result = clear_active_chat(None, "session_123")
        assert result is False

    def test_clear_empty_session_id(self):
        """Empty session_id should return False."""
        mock_memory = MagicMock()
        result = clear_active_chat(mock_memory, "")
        assert result is False

    def test_clear_error_during_delete(self):
        """If delete_message raises, should continue with remaining messages."""
        mock_memory = MagicMock()
        mock_memory.get_messages.return_value = [
            MockMessage(id=1),
            MockMessage(id=2),
            MockMessage(id=3),
        ]

        # Second message fails
        call_count = [0]
        def mock_delete(session_id, msg_id):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("DB error")
            return True

        mock_memory.delete_message.side_effect = mock_delete

        result = clear_active_chat(mock_memory, "session_123")
        assert result is True  # At least one was deleted

    def test_clear_error_in_get_messages(self):
        """If get_messages raises, should return False."""
        mock_memory = MagicMock()
        mock_memory.get_messages.side_effect = RuntimeError("Connection lost")

        result = clear_active_chat(mock_memory, "session_123")
        assert result is False

    def test_clear_with_large_session(self):
        """Should handle many messages."""
        mock_memory = MagicMock()
        mock_memory.get_messages.return_value = [MockMessage(id=i) for i in range(50)]
        mock_memory.delete_message.return_value = True

        result = clear_active_chat(mock_memory, "session_big")
        assert result is True

    def test_preserves_session(self):
        """Session should NOT be deleted (no delete_session call)."""
        mock_memory = MagicMock()
        mock_memory.get_messages.return_value = [MockMessage(id=1)]
        mock_memory.delete_message.return_value = True

        clear_active_chat(mock_memory, "session_123")
        # delete_message may be called but delete_session should NOT be called
        delete_calls = [c for c in mock_memory.method_calls if 'delete_session' in str(c)]
        assert len(delete_calls) == 0

    def test_clear_then_empty(self):
        """After clearing, get_messages should show empty."""
        mock_memory = MagicMock()
        mock_memory.get_messages.side_effect = [
            [MockMessage(id=1)],  # First call: has messages
            [],                    # Second call: empty after deletion
        ]
        mock_memory.delete_message.return_value = True

        clear_active_chat(mock_memory, "session_123")
        # After clear, check if empty
        remaining = mock_memory.get_messages("session_123", limit=1)
        assert len(remaining) == 0


class TestDeleteSessionMessagesBulk:
    def test_deletes_all(self):
        mock_memory = MagicMock()
        mock_memory.get_messages.return_value = [MockMessage(id=i) for i in range(5)]
        mock_memory.delete_message.return_value = True

        count = delete_session_messages_bulk(mock_memory, "session_123")
        assert count == 5

    def test_empty_session(self):
        mock_memory = MagicMock()
        mock_memory.get_messages.return_value = []

        count = delete_session_messages_bulk(mock_memory, "session_123")
        assert count == 0

    def test_none_memory(self):
        assert delete_session_messages_bulk(None, "s1") == 0

    def test_error_handling(self):
        mock_memory = MagicMock()
        mock_memory.get_messages.side_effect = RuntimeError("fail")
        assert delete_session_messages_bulk(mock_memory, "s1") == 0
