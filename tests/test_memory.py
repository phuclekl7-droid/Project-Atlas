"""
Unit tests for the Memory module.

Uses a temporary SQLite file (not the real data/memory.db) for testing.
Tests cover:
- Session creation, retrieval, listing, deletion
- Message adding, retrieval, context formatting
- Edge cases: empty sessions, missing sessions, duplicate operations
- get_total_stats and get_context_text
"""

import os
import sqlite3

import pytest

from src.memory import Memory, Message, Session, _now


# ── Helper to create a memory with a temp db path ──
@pytest.fixture
def memory(tmp_path):
    """Create a Memory instance backed by a temporary SQLite file."""
    db_path = tmp_path / "test_memory.db"
    mem = Memory(str(db_path))
    yield mem
    mem.close()
    if os.path.exists(str(db_path)):
        os.remove(str(db_path))


# ============================================================
# Session Management
# ============================================================


class TestCreateSession:
    def test_create_session_returns_string_id(self, memory):
        """create_session should return a string ID."""
        session_id = memory.create_session()
        assert isinstance(session_id, str)
        assert len(session_id) == 8  # UUID4 truncated to 8 chars

    def test_create_session_with_name(self, memory):
        """create_session should accept a custom name."""
        session_id = memory.create_session(name="My Chat")
        session = memory.get_session(session_id)
        assert session is not None
        assert session.name == "My Chat"

    def test_create_session_default_name(self, memory):
        """create_session without name should generate one."""
        session_id = memory.create_session()
        session = memory.get_session(session_id)
        assert session is not None
        assert session.name.startswith("Session ")

    def test_create_multiple_sessions(self, memory):
        """Multiple sessions should each have unique IDs."""
        id1 = memory.create_session()
        id2 = memory.create_session()
        assert id1 != id2


class TestGetSession:
    def test_get_existing_session(self, memory):
        """get_session should return a Session object for existing session."""
        session_id = memory.create_session(name="Test")
        session = memory.get_session(session_id)
        assert isinstance(session, Session)
        assert session.id == session_id
        assert session.name == "Test"
        assert session.message_count == 0

    def test_get_nonexistent_session(self, memory):
        """get_session should return None for non-existent session."""
        session = memory.get_session("nonexistent")
        assert session is None


class TestListSessions:
    def test_list_empty(self, memory):
        """list_sessions should return empty list when no sessions exist."""
        sessions = memory.list_sessions()
        assert sessions == []

    def test_list_multiple_sessions(self, memory):
        """list_sessions should return all sessions, newest first."""
        id1 = memory.create_session(name="First")
        id2 = memory.create_session(name="Second")
        sessions = memory.list_sessions()
        assert len(sessions) == 2
        # Second is newer, should be first
        assert sessions[0].id == id2
        assert sessions[1].id == id1

    def test_list_with_limit(self, memory):
        """list_sessions should respect the limit parameter."""
        for i in range(10):
            memory.create_session(name=f"Session {i}")
        sessions = memory.list_sessions(limit=3)
        assert len(sessions) == 3


class TestDeleteSession:
    def test_delete_existing_session(self, memory):
        """delete_session should return True and remove the session."""
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "Hello")
        assert memory.count_messages(session_id) == 1

        result = memory.delete_session(session_id)
        assert result is True
        assert memory.get_session(session_id) is None
        # Messages should be cascade deleted too
        assert memory.count_messages(session_id) == 0

    def test_delete_nonexistent_session(self, memory):
        """delete_session should return False for non-existent session."""
        result = memory.delete_session("nonexistent")
        assert result is False

    def test_delete_all_sessions(self, memory):
        """delete_all_sessions should remove all sessions and return count."""
        memory.create_session()
        memory.create_session()
        memory.create_session()
        count = memory.delete_all_sessions()
        assert count == 3
        assert len(memory.list_sessions()) == 0


# ============================================================
# Message Management
# ============================================================


class TestAddMessage:
    def test_add_user_message(self, memory):
        """add_message should create a Message with role 'user'."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Hello!")
        assert isinstance(msg, Message)
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.session_id == session_id
        assert msg.id > 0

    def test_add_assistant_message(self, memory):
        """add_message should work for assistant role."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "assistant", "Hi there!")
        assert msg.role == "assistant"

    def test_add_message_increments_count(self, memory):
        """Adding messages should update session message_count."""
        session_id = memory.create_session()
        assert memory.get_session(session_id).message_count == 0
        memory.add_message(session_id, "user", "A")
        assert memory.get_session(session_id).message_count == 1
        memory.add_message(session_id, "assistant", "B")
        assert memory.get_session(session_id).message_count == 2

    def test_add_message_updates_timestamp(self, memory):
        """Adding a message should update session updated_at."""
        session_id = memory.create_session()
        old = memory.get_session(session_id).updated_at
        memory.add_message(session_id, "user", "Test")
        new = memory.get_session(session_id).updated_at
        # The timestamp should be different (or at least not empty)
        assert new >= old


class TestGetMessages:
    def test_get_messages_returns_all(self, memory):
        """get_messages should return all messages in order."""
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "Q1")
        memory.add_message(session_id, "assistant", "A1")
        memory.add_message(session_id, "user", "Q2")

        messages = memory.get_messages(session_id)
        assert len(messages) == 3
        assert messages[0].content == "Q1"
        assert messages[1].content == "A1"
        assert messages[2].content == "Q2"

    def test_get_messages_with_limit(self, memory):
        """get_messages should respect the limit."""
        session_id = memory.create_session()
        for i in range(10):
            memory.add_message(session_id, "user", f"Msg {i}")
        messages = memory.get_messages(session_id, limit=3)
        assert len(messages) == 3
        # Oldest first
        assert messages[0].content == "Msg 0"
        assert messages[2].content == "Msg 2"

    def test_get_messages_empty_session(self, memory):
        """get_messages should return empty list for session with no messages."""
        session_id = memory.create_session()
        messages = memory.get_messages(session_id)
        assert messages == []


# ============================================================
# Context Formatting
# ============================================================


class TestGetContext:
    def test_get_context_basic(self, memory):
        """get_context should return list of {role, content} dicts."""
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "Hello")
        memory.add_message(session_id, "assistant", "Hi!")
        context = memory.get_context(session_id)
        assert len(context) == 2
        assert context[0] == {"role": "user", "content": "Hello"}
        assert context[1] == {"role": "assistant", "content": "Hi!"}

    def test_get_context_respects_limit(self, memory):
        """get_context should return only the N most recent messages."""
        session_id = memory.create_session()
        for i in range(10):
            memory.add_message(session_id, "user", f"Msg {i}")
            memory.add_message(session_id, "assistant", f"Ans {i}")
        context = memory.get_context(session_id, limit=4)
        assert len(context) == 4
        # Should be the 4 most recent: Msg 8, Ans 8, Msg 9, Ans 9
        assert context[-1]["content"] == "Ans 9"

    def test_get_context_empty(self, memory):
        """get_context should return empty list for session with no messages."""
        session_id = memory.create_session()
        assert memory.get_context(session_id) == []


class TestGetContextText:
    def test_get_context_text_format(self, memory):
        """get_context_text should format as 'Role: Content' lines."""
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "Hello")
        memory.add_message(session_id, "assistant", "Hi!")
        text = memory.get_context_text(session_id)
        assert "User: Hello" in text
        assert "Assistant: Hi!" in text

    def test_get_context_text_empty(self, memory):
        """get_context_text should return empty string for empty session."""
        session_id = memory.create_session()
        assert memory.get_context_text(session_id) == ""


# ============================================================
# Message Editing & Deletion
# ============================================================


class TestGetMessageById:
    def test_get_existing_message(self, memory):
        """get_message_by_id should return a Message for an existing message."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Hello!")
        found = memory.get_message_by_id(session_id, msg.id)
        assert found is not None
        assert found.id == msg.id
        assert found.content == "Hello!"
        assert found.role == "user"

    def test_get_nonexistent_message(self, memory):
        """get_message_by_id should return None for non-existent message."""
        session_id = memory.create_session()
        found = memory.get_message_by_id(session_id, 999)
        assert found is None

    def test_get_message_wrong_session(self, memory):
        """get_message_by_id should return None if message exists but in different session."""
        s1 = memory.create_session()
        s2 = memory.create_session()
        msg = memory.add_message(s1, "user", "Hello")
        found = memory.get_message_by_id(s2, msg.id)
        assert found is None


class TestUpdateMessage:
    def test_update_content(self, memory):
        """update_message should update the message content."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Original content")
        updated = memory.update_message(session_id, msg.id, "Updated content")
        assert updated is not None
        assert updated.content == "Updated content"
        # Verify persistence
        fetched = memory.get_message_by_id(session_id, msg.id)
        assert fetched.content == "Updated content"

    def test_update_not_found(self, memory):
        """update_message on non-existent message should return None."""
        session_id = memory.create_session()
        result = memory.update_message(session_id, 999, "New content")
        assert result is None

    def test_update_empty_content_raises(self, memory):
        """update_message with empty content should raise AssistantError."""
        from src.core import AssistantError
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Hello")
        with pytest.raises(AssistantError, match="cannot be empty"):
            memory.update_message(session_id, msg.id, "")
        with pytest.raises(AssistantError, match="cannot be empty"):
            memory.update_message(session_id, msg.id, "   ")

    def test_update_does_not_change_message_count(self, memory):
        """update_message should NOT increment message_count (editing, not adding)."""
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "A")
        memory.add_message(session_id, "assistant", "B")
        msg = memory.add_message(session_id, "user", "C")
        assert memory.get_session(session_id).message_count == 3
        memory.update_message(session_id, msg.id, "Updated C")
        assert memory.get_session(session_id).message_count == 3


class TestDeleteMessage:
    def test_delete_existing_message(self, memory):
        """delete_message should remove the message and return it."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Hello!")
        deleted = memory.delete_message(session_id, msg.id)
        assert deleted is not None
        assert deleted.id == msg.id
        assert deleted.content == "Hello!"
        # Verify deletion
        assert memory.get_message_by_id(session_id, msg.id) is None

    def test_delete_not_found(self, memory):
        """delete_message on non-existent message should return None."""
        session_id = memory.create_session()
        result = memory.delete_message(session_id, 999)
        assert result is None

    def test_delete_decrements_count(self, memory):
        """delete_message should decrement session message_count."""
        session_id = memory.create_session()
        msg1 = memory.add_message(session_id, "user", "A")
        msg2 = memory.add_message(session_id, "assistant", "B")
        assert memory.get_session(session_id).message_count == 2
        memory.delete_message(session_id, msg1.id)
        assert memory.get_session(session_id).message_count == 1
        memory.delete_message(session_id, msg2.id)
        assert memory.get_session(session_id).message_count == 0

    def test_delete_decrements_not_below_zero(self, memory):
        """delete_message should not decrement message_count below 0."""
        session_id = memory.create_session()
        # message_count should be 0, try to delete non-existent
        memory.delete_message(session_id, 999)
        assert memory.get_session(session_id).message_count == 0

    def test_delete_returns_correct_role(self, memory):
        """delete_message should return the correct message with original role."""
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "Hi")
        msg2 = memory.add_message(session_id, "assistant", "Hello there")
        deleted = memory.delete_message(session_id, msg2.id)
        assert deleted.role == "assistant"
        assert deleted.content == "Hello there"


# ============================================================
# Pinned Messages
# ============================================================


class TestPinMessage:
    def test_pin_existing_message(self, memory):
        """pin_message should set pinned=1 on a message."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Important!")
        pinned = memory.pin_message(session_id, msg.id)
        assert pinned is not None
        assert pinned.pinned == 1
        # Verify persistence
        fetched = memory.get_message_by_id(session_id, msg.id)
        assert fetched.pinned == 1

    def test_pin_nonexistent_message(self, memory):
        """pin_message on non-existent message should return None."""
        session_id = memory.create_session()
        result = memory.pin_message(session_id, 999)
        assert result is None

    def test_pin_wrong_session(self, memory):
        """pin_message should return None if message in different session."""
        s1 = memory.create_session()
        s2 = memory.create_session()
        msg = memory.add_message(s1, "user", "Hello")
        result = memory.pin_message(s2, msg.id)
        assert result is None


class TestUnpinMessage:
    def test_unpin_existing_pinned_message(self, memory):
        """unpin_message should set pinned=0."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "assistant", "Important")
        memory.pin_message(session_id, msg.id)
        unpinned = memory.unpin_message(session_id, msg.id)
        assert unpinned is not None
        assert unpinned.pinned == 0
        # Verify persistence
        fetched = memory.get_message_by_id(session_id, msg.id)
        assert fetched.pinned == 0

    def test_unpin_non_pinned_message(self, memory):
        """unpin_message should work on a message that isn't pinned."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Hello")
        unpinned = memory.unpin_message(session_id, msg.id)
        assert unpinned is not None
        assert unpinned.pinned == 0

    def test_unpin_nonexistent_message(self, memory):
        """unpin_message on non-existent message should return None."""
        session_id = memory.create_session()
        result = memory.unpin_message(session_id, 999)
        assert result is None


class TestGetPinnedMessages:
    def test_get_pinned_messages_empty(self, memory):
        """get_pinned_messages should return empty list when nothing pinned."""
        session_id = memory.create_session()
        pinned = memory.get_pinned_messages(session_id)
        assert pinned == []

    def test_get_pinned_messages_returns_pinned_only(self, memory):
        """get_pinned_messages should only return pinned messages."""
        session_id = memory.create_session()
        msg1 = memory.add_message(session_id, "user", "Not pinned")
        msg2 = memory.add_message(session_id, "user", "Pinned!")
        msg3 = memory.add_message(session_id, "assistant", "Also pinned")
        memory.pin_message(session_id, msg2.id)
        memory.pin_message(session_id, msg3.id)

        pinned = memory.get_pinned_messages(session_id)
        assert len(pinned) == 2
        assert pinned[0].id == msg2.id
        assert pinned[1].id == msg3.id

    def test_get_pinned_messages_ordered_by_id(self, memory):
        """get_pinned_messages should return in insertion order (oldest first)."""
        session_id = memory.create_session()
        msg1 = memory.add_message(session_id, "user", "First")
        msg2 = memory.add_message(session_id, "assistant", "Second")
        msg3 = memory.add_message(session_id, "user", "Third")
        # Pin out of order
        memory.pin_message(session_id, msg3.id)
        memory.pin_message(session_id, msg1.id)

        pinned = memory.get_pinned_messages(session_id)
        assert pinned[0].id == msg1.id  # Oldest first
        assert pinned[1].id == msg3.id

    def test_get_pinned_messages_after_unpin(self, memory):
        """get_pinned_messages should exclude unpinned messages."""
        session_id = memory.create_session()
        msg1 = memory.add_message(session_id, "user", "Pin me")
        msg2 = memory.add_message(session_id, "user", "And me")
        memory.pin_message(session_id, msg1.id)
        memory.pin_message(session_id, msg2.id)
        assert len(memory.get_pinned_messages(session_id)) == 2

        memory.unpin_message(session_id, msg1.id)
        pinned = memory.get_pinned_messages(session_id)
        assert len(pinned) == 1
        assert pinned[0].id == msg2.id

    def test_get_pinned_messages_other_session_unaffected(self, memory):
        """Pinning in one session should not affect another."""
        s1 = memory.create_session()
        s2 = memory.create_session()
        m1 = memory.add_message(s1, "user", "Important")
        m2 = memory.add_message(s2, "user", "Not pinned")
        memory.pin_message(s1, m1.id)

        assert len(memory.get_pinned_messages(s1)) == 1
        assert len(memory.get_pinned_messages(s2)) == 0


class TestPinnedToDict:
    def test_to_dict_includes_pinned(self, memory):
        """Message.to_dict should include pinned field."""
        session_id = memory.create_session()
        msg = memory.add_message(session_id, "user", "Hello")
        pinned = memory.pin_message(session_id, msg.id)
        d = pinned.to_dict()
        assert d.get("pinned") == 1

    def test_to_dict_pinned_not_pinned(self, memory):
        """Message.to_dict should show pinned=0 for non-pinned messages."""
        from src.memory import Message
        msg = Message(id=1, session_id="abc", role="user", content="Hello",
                       created_at="2026-01-01T00:00:00Z")
        d = msg.to_dict()
        assert d.get("pinned") == 0


# ============================================================
# Edge Cases
# ============================================================


class TestEdgeCases:
    def test_add_message_to_nonexistent_session(self, memory):
        """Adding a message to non-existent session should raise IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            memory.add_message("nonexistent", "user", "test")

    def test_count_messages_empty_session(self, memory):
        """count_messages should return 0 for empty session."""
        session_id = memory.create_session()
        assert memory.count_messages(session_id) == 0

    def test_count_messages_multiple(self, memory):
        """count_messages should return correct count."""
        session_id = memory.create_session()
        for i in range(5):
            memory.add_message(session_id, "user", f"M{i}")
        assert memory.count_messages(session_id) == 5

    def test_double_delete_session(self, memory):
        """Deleting an already-deleted session should return False."""
        session_id = memory.create_session()
        assert memory.delete_session(session_id) is True
        assert memory.delete_session(session_id) is False

    def test_get_total_stats_empty(self, memory):
        """get_total_stats should show zero for empty database."""
        stats = memory.get_total_stats()
        assert stats["sessions"] == 0
        assert stats["messages"] == 0
        assert "db_path" in stats

    def test_get_total_stats_after_operations(self, memory):
        """get_total_stats should reflect actual counts."""
        s1 = memory.create_session()
        s2 = memory.create_session()
        memory.add_message(s1, "user", "A")
        memory.add_message(s1, "assistant", "B")
        memory.add_message(s2, "user", "C")
        stats = memory.get_total_stats()
        assert stats["sessions"] == 2
        assert stats["messages"] == 3


# ============================================================
# Message & Session Data Models
# ============================================================


class TestMessageModel:
    def test_to_dict(self):
        """Message.to_dict should return all fields."""
        msg = Message(id=1, session_id="abc", role="user", content="Hello",
                       created_at="2026-01-01T00:00:00Z", tokens=10)
        d = msg.to_dict()
        assert d["id"] == 1
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert d["tokens"] == 10

    def test_to_context_dict(self):
        """Message.to_context_dict should return {role, content}."""
        msg = Message(id=1, session_id="abc", role="user", content="Hello",
                       created_at="2026-01-01T00:00:00Z")
        assert msg.to_context_dict() == {"role": "user", "content": "Hello"}

    def test_repr(self):
        """Message.__repr__ should show role and truncated content."""
        msg = Message(id=1, session_id="abc", role="user", content="Hello world",
                       created_at="2026-01-01T00:00:00Z")
        r = repr(msg)
        assert "user" in r
        assert "Hello" in r


class TestSessionModel:
    def test_to_dict(self):
        """Session.to_dict should return all fields."""
        s = Session(id="abc", name="Test", created_at="t1", updated_at="t2", message_count=5)
        d = s.to_dict()
        assert d["id"] == "abc"
        assert d["name"] == "Test"
        assert d["message_count"] == 5

    def test_repr(self):
        """Session.__repr__ should show ID, name, and message count."""
        s = Session(id="abc", name="My Chat", created_at="t1", updated_at="t2", message_count=3)
        r = repr(s)
        assert "abc" in r
        assert "My Chat" in r
        assert "3" in r


# ============================================================
# Context Manager
# ============================================================


class TestContextManager:
    def test_context_manager_closes_connection(self, tmp_path):
        """Using Memory as a context manager should close the connection."""
        db_path = tmp_path / "ctx_test.db"
        with Memory(str(db_path)) as mem:
            session_id = mem.create_session()
            mem.add_message(session_id, "user", "test")
            # Connection should be open
            assert mem._connection is not None
        # After exit, connection should be closed
        assert mem._connection is None
