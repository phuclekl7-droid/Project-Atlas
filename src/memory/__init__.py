"""
Memory module: Manages short-term and long-term conversation history and context.

Uses SQLite (built-in) for persistent storage of chat sessions and messages.
Supports session management, context retrieval, and automatic pruning.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.core import AssistantError, setup_logger

logger = setup_logger("memory")


# ============================================================
# Helpers
# ============================================================


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# Data Models
# ============================================================


class Message:
    """Represents a single message in a conversation."""

    def __init__(
        self,
        id: int,
        session_id: str,
        role: str,
        content: str,
        created_at: str,
        tokens: int = 0,
    ):
        self.id = id
        self.session_id = session_id
        self.role = role
        self.content = content
        self.created_at = created_at
        self.tokens = tokens

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "tokens": self.tokens,
        }

    def to_context_dict(self) -> dict:
        """Format for sending as context to an LLM (role/content pairs)."""
        return {"role": self.role, "content": self.content}

    def __repr__(self) -> str:
        preview = self.content[:50] + ("..." if len(self.content) > 50 else "")
        return f"Message(id={self.id}, role={self.role!r}, content={preview!r})"


class Session:
    """Represents a chat session with metadata."""

    def __init__(
        self,
        id: str,
        name: str,
        created_at: str,
        updated_at: str,
        message_count: int = 0,
    ):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.updated_at = updated_at
        self.message_count = message_count

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
        }

    def __repr__(self) -> str:
        return (
            f"Session(id={self.id!r}, name={self.name!r}, "
            f"messages={self.message_count})"
        )


# ============================================================
# SQLite Memory Store
# ============================================================


class Memory:
    """
    SQLite-backed memory store for chat sessions and messages.

    Usage:
        memory = Memory("data/memory.db")
        session_id = memory.create_session()
        memory.add_message(session_id, "user", "Hello!")
        context = memory.get_context(session_id)
    """

    def __init__(self, db_path: str = "data/memory.db"):
        self.db_path = str(db_path)

        # Ensure parent directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[sqlite3.Connection] = None
        self._initialize_db()

        logger.info(f"Memory initialized: {self.db_path}")

    # ── Database Connection ──

    @property
    def connection(self) -> sqlite3.Connection:
        """Lazy-initialized database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
        return self._connection

    def _initialize_db(self) -> None:
        """Create tables if they don't exist."""
        conn = self.connection
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL,
                message_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content     TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                tokens      INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id);
        """)
        conn.commit()

    # ── Session Management ──

    def create_session(self, name: Optional[str] = None) -> str:
        """
        Create a new chat session.

        Args:
            name: Optional human-readable name (e.g., "Chat về Python")

        Returns:
            Session ID string
        """
        session_id = str(uuid.uuid4())[:8]
        now = _now()
        name = name or f"Session {session_id}"

        self.connection.execute(
            "INSERT INTO sessions (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, name, now, now),
        )
        self.connection.commit()
        logger.debug(f"Created session: {session_id} ({name!r})")
        return session_id

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session metadata by ID, or None if not found."""
        row = self.connection.execute(
            "SELECT id, name, created_at, updated_at, message_count "
            "FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if row is None:
            return None
        return Session(**dict(row))

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[Session]:
        """List recent sessions, newest first."""
        rows = self.connection.execute(
            "SELECT id, name, created_at, updated_at, message_count "
            "FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [Session(**dict(r)) for r in rows]

    def update_session_name(self, session_id: str, name: str) -> None:
        """Update the human-readable name of a session."""
        self.connection.execute(
            "UPDATE sessions SET name = ? WHERE id = ?",
            (name, session_id),
        )
        self.connection.commit()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages. Returns True if deleted."""
        cursor = self.connection.execute(
            "DELETE FROM sessions WHERE id = ?", (session_id,)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_all_sessions(self) -> int:
        """Delete ALL sessions and messages. Returns count of deleted sessions."""
        count = self.connection.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]
        self.connection.execute("DELETE FROM sessions")
        self.connection.commit()
        logger.warning(f"Deleted all {count} sessions")
        return count

    # ── Message Management ──

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
    ) -> Message:
        """
        Add a message to a session.

        Args:
            session_id: Target session ID
            role: "user", "assistant", or "system"
            content: Message text content
            tokens: Optional token count for tracking

        Returns:
            The newly created Message
        """
        now = _now()

        # Insert message
        cursor = self.connection.execute(
            "INSERT INTO messages (session_id, role, content, created_at, tokens) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, now, tokens),
        )

        # Update session metadata
        self.connection.execute(
            "UPDATE sessions SET updated_at = ?, message_count = message_count + 1 "
            "WHERE id = ?",
            (now, session_id),
        )
        self.connection.commit()

        message = Message(
            id=cursor.lastrowid,
            session_id=session_id,
            role=role,
            content=content,
            created_at=now,
            tokens=tokens,
        )
        logger.debug(f"Added message {message.id} to session {session_id}")
        return message

    def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages from a session, oldest first."""
        rows = self.connection.execute(
            "SELECT id, session_id, role, content, created_at, tokens "
            "FROM messages WHERE session_id = ? "
            "ORDER BY id ASC LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        ).fetchall()
        return [Message(**dict(r)) for r in rows]

    def get_context(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get recent messages formatted as context for an LLM.

        Returns a list of {role, content} dicts, oldest first within the window.
        This is ready to be injected into Ollama/OpenAI chat-style calls.

        Args:
            session_id: Session to get context from
            limit: Number of most recent messages to include

        Returns:
            List of {"role": str, "content": str} dicts
        """
        messages = self.get_messages(session_id, limit=limit)
        return [m.to_context_dict() for m in messages]

    def get_context_text(
        self,
        session_id: str,
        limit: int = 10,
    ) -> str:
        """
        Get recent messages formatted as plain text for simple models.

        Returns a string like:
          User: Hello
          Assistant: Hi there!
          User: How are you?

        Args:
            session_id: Session to get context from
            limit: Number of most recent messages to include

        Returns:
            Formatted context string
        """
        context = self.get_context(session_id, limit=limit)
        lines = []
        for msg in context:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

    def count_messages(self, session_id: str) -> int:
        """Count total messages in a session."""
        row = self.connection.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return row[0] if row else 0

    def get_total_stats(self) -> dict:
        """Get overall memory statistics."""
        session_count = self.connection.execute(
            "SELECT COUNT(*) FROM sessions"
        ).fetchone()[0]
        message_count = self.connection.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]
        return {
            "sessions": session_count,
            "messages": message_count,
            "db_path": self.db_path,
        }

    # ── Cleanup ──

    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.debug("Memory database connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
