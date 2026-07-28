"""
Session Cloner (Feature: Clone Chat Session)

Creates a duplicate of a chat session with all its messages copied
into a new session with name "[Copy] Original Name".

Usage (from sidebar button):
    from handlers.session_cloner import clone_session
    new_id = clone_session(session_id)
    st.session_state.session_id = new_id
    st.rerun()

Dependencies:
    - src.memory.Memory (session management, get_messages, create_session, add_message)
"""

import time
from typing import Optional


def clone_session(
    memory,
    source_session_id: str,
    new_name: Optional[str] = None,
    max_messages: int = 200,
) -> Optional[str]:
    """
    Clone a chat session: copy all messages from source to a new session.

    Args:
        memory: Memory instance (from st.session_state.memory)
        source_session_id: ID of the session to clone
        new_name: Optional name for the new session.
                  If None, generates "[Copy] OriginalName"
        max_messages: Maximum number of messages to copy (default 200)

    Returns:
        New session_id string if successful, None on failure.

    Usage:
        new_id = clone_session(memory, source_session_id)
        if new_id:
            st.session_state.session_id = new_id
            st.rerun()
    """
    if not memory or not source_session_id:
        return None

    try:
        # Get source session info
        source_session = memory.get_session(source_session_id)
        if source_session is None:
            return None

        source_name = source_session.name or "Untitled"

        # Determine new session name
        if new_name is None:
            new_name = f"[Copy] {source_name}"

        # Create the new session
        new_session_id = memory.create_session(name=new_name)

        if not new_session_id:
            return None

        # Get messages from source
        messages = memory.get_messages(source_session_id, limit=max_messages)

        if not messages:
            return new_session_id  # Empty session, still cloned

        # Copy each message to the new session
        copied_count = 0
        for msg in messages:
            try:
                # Preserve role, content, and provider
                provider = getattr(msg, "provider", None)
                if provider:
                    memory.add_message(
                        new_session_id,
                        msg.role,
                        msg.content,
                        provider=provider,
                    )
                else:
                    memory.add_message(new_session_id, msg.role, msg.content)
                copied_count += 1
            except Exception:
                continue  # Skip problematic messages

        return new_session_id

    except Exception as e:
        return None


def get_clone_name_suggestion(memory, source_session_id: str) -> str:
    """
    Get the suggested name for a cloned session.

    Args:
        memory: Memory instance
        source_session_id: ID of the source session

    Returns:
        Suggested name string like "[Copy] OriginalName"
    """
    try:
        session = memory.get_session(source_session_id)
        if session:
            return f"[Copy] {session.name or 'Untitled'}"
    except Exception:
        pass
    return "[Copy] Session"
