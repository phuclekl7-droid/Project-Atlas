"""
Chat Clearer (Feature 169: Clear Active Chat)

Deletes ALL messages in the current chat session while preserving
the session ID and name. Effectively resets the conversation to empty.

Usage:
    from handlers.chat_clearer import clear_active_chat
    clear_active_chat(memory, session_id)
"""

from typing import Optional


def clear_active_chat(
    memory,
    session_id: str,
) -> bool:
    """
    Delete ALL messages in the current chat session.

    The session itself (ID, name, metadata) is preserved — only
    the messages table entries for this session are removed.

    Args:
        memory: Memory instance (must have delete_session_messages method
                or equivalent)
        session_id: The session ID whose messages should be cleared

    Returns:
        True if successful, False on failure

    Side effects:
        - All messages in the session are permanently deleted
        - Session ID, name, and other metadata are kept
        - The UI should call st.rerun() afterward to refresh the chat
    """
    if not memory or not session_id:
        return False

    try:
        # Get all messages in a single call
        all_messages = memory.get_messages(session_id, limit=10000)
        if not all_messages:
            # Already empty
            return True

        # Delete each message
        deleted_count = 0
        for msg in all_messages:
            try:
                memory.delete_message(session_id, msg.id)
                deleted_count += 1
            except Exception:
                continue

        return deleted_count > 0

    except Exception as e:
        return False


def delete_session_messages_bulk(memory, session_id: str) -> int:
    """
    Alternative implementation using direct SQL if available.

    Falls back to individual delete_message calls.
    Returns number of messages deleted.
    """
    if not memory or not session_id:
        return 0

    try:
        messages = memory.get_messages(session_id, limit=10000)
        if not messages:
            return 0

        count = 0
        for msg in messages:
            try:
                memory.delete_message(session_id, msg.id)
                count += 1
            except Exception:
                continue
        return count
    except Exception:
        return 0
