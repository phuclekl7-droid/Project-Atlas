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
from src.core.token_counter import TokenCounter

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

    _IMAGE_PREFIX = "[IMAGE:"
    _IMAGE_SUFFIX = "]"

    def __init__(
        self,
        id: int,
        session_id: str,
        role: str,
        content: str,
        created_at: str,
        tokens: int = 0,
        provider: Optional[str] = None,
        pinned: int = 0,
    ):
        self.id = id
        self.session_id = session_id
        self.role = role
        self.content = content
        self.created_at = created_at
        self.tokens = tokens
        self.provider = provider
        self.pinned = pinned

    @property
    def image_path(self) -> Optional[str]:
        """Extract single image path from content.

        Returns the first image path if any, None otherwise.
        For backward compatibility — prefer image_paths for multi-image.
        """
        paths = self.image_paths
        return paths[0] if paths else None

    @property
    def image_paths(self) -> list[str]:
        """Extract ALL image paths from content if this message contains images.

        Parses all [IMAGE:path/to/image] markers in the content.
        Returns an empty list if no images found.
        """
        paths = []
        remaining = self.content
        while self._IMAGE_PREFIX in remaining:
            start = remaining.find(self._IMAGE_PREFIX) + len(self._IMAGE_PREFIX)
            end = remaining.find(self._IMAGE_SUFFIX, start)
            if end > start:
                paths.append(remaining[start:end])
                remaining = remaining[end + len(self._IMAGE_SUFFIX):]
            else:
                break
        return paths

    @property
    def images_count(self) -> int:
        """Number of images in this message."""
        return len(self.image_paths)

    @property
    def text_content(self) -> str:
        """Get the text portion of the message, stripping all image references."""
        text = self.content
        while self._IMAGE_PREFIX in text:
            start = text.find(self._IMAGE_PREFIX)
            end = text.find(self._IMAGE_SUFFIX, start)
            if end > start:
                text = text[:start] + text[end + len(self._IMAGE_SUFFIX):]
            else:
                break
        return text.strip()

    def has_image(self) -> bool:
        """Check if this message contains one or more image references."""
        return len(self.image_paths) > 0

    @staticmethod
    def make_image_content(image_path: str, text: str = "") -> str:
        """
        Create message content string that includes a single image reference.

        Format: [IMAGE:path/to/image.jpg]Text prompt
        The text portion is optional — can be empty for just the image.
        """
        if text:
            return f"{Message._IMAGE_PREFIX}{image_path}{Message._IMAGE_SUFFIX}{text}"
        return f"{Message._IMAGE_PREFIX}{image_path}{Message._IMAGE_SUFFIX}"

    @staticmethod
    def make_images_content(image_paths: list[str], text: str = "") -> str:
        """
        Create message content string that includes MULTIPLE image references.

        Format: [IMAGE:path1][IMAGE:path2]Text prompt
        All image refs come first, followed by the optional text prompt.
        """
        img_part = "".join(
            f"{Message._IMAGE_PREFIX}{p}{Message._IMAGE_SUFFIX}"
            for p in image_paths
        )
        if text:
            return f"{img_part}{text}"
        return img_part

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "tokens": self.tokens,
            "pinned": self.pinned,
        }
        if self.provider is not None:
            d["provider"] = self.provider
        if self.has_image():
            d["image_path"] = self.image_path
        return d

    def to_context_dict(self) -> dict:
        """Format for sending as context to an LLM (role/content pairs).

        For messages with images, the text_content (without image ref) is used.
        The image is handled separately by the model provider's vision methods.
        """
        return {"role": self.role, "content": self.text_content}

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
        auto_named: int = 0,
    ):
        self.id = id
        self.name = name
        self.created_at = created_at
        self.updated_at = updated_at
        self.message_count = message_count
        self.auto_named = auto_named

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
        """Lazy-initialized database connection.

        Uses check_same_thread=False to support Streamlit Cloud,
        which may rerun the app on a different thread.
        """
        if self._connection is None:
            self._connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
            )
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
                provider    TEXT DEFAULT NULL,
                pinned      INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id);
        """)

        # Migration: add provider column for existing databases
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN provider TEXT DEFAULT NULL")
            logger.debug("Added 'provider' column to existing messages table (migration)")
        except Exception:
            pass  # Column already exists — ignore

        # Migration: add pinned column for existing databases
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN pinned INTEGER DEFAULT 0")
            logger.debug("Added 'pinned' column to existing messages table (migration)")
        except Exception:
            pass  # Column already exists — ignore

        # Migration: add preferences table for user preference memory
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)

        # Migration: add prompt_tokens and completion_tokens for cost tracking (Feature 157)
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN prompt_tokens INTEGER DEFAULT 0")
            logger.debug("Added 'prompt_tokens' column (migration)")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN completion_tokens INTEGER DEFAULT 0")
            logger.debug("Added 'completion_tokens' column (migration)")
        except Exception:
            pass

        # Migration: create snippets table for Code Snippet Vault (Feature 158)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snippets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                language    TEXT NOT NULL DEFAULT '',
                code        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        # Migration: add auto_named column for session naming (Feature 156)
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN auto_named INTEGER DEFAULT 0")
            logger.debug("Added 'auto_named' column to sessions (migration)")
        except Exception:
            pass

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
            "FROM sessions ORDER BY updated_at DESC, rowid DESC LIMIT ? OFFSET ?",
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

    # ── Auto Session Naming ──

    def _auto_name_session(self, session_id: str, content: str) -> None:
        """
        Auto-generate a short session title from the first user message (Feature 156).

        Uses the first ~50 chars of the first user message as the session title.
        Only sets the name on the first message if the session hasn't been renamed yet.
        """
        session = self.get_session(session_id)
        if session is None:
            return
        # Only auto-name if message_count is 0 (first message) and not already auto-named
        if session.message_count == 0 and not getattr(session, 'auto_named', False):
            # Generate short title from first message
            title = content.strip()[:50]
            # Clean up the title
            title = title.split('\n')[0]  # First line only
            title = title.strip()
            if len(title) > 45:
                title = title[:42] + '...'
            if title:
                self.update_session_name(session_id, title)
                self.connection.execute(
                    "UPDATE sessions SET auto_named = 1 WHERE id = ?",
                    (session_id,),
                )
                self.connection.commit()

    # ── Token Cost Calculation ──

    PROVIDER_COST_TABLE = {
        "openai": {"input": 5.0 / 1_000_000, "output": 15.0 / 1_000_000},  # GPT-4o
        "gemini": {"input": 1.25 / 1_000_000, "output": 5.0 / 1_000_000},  # Gemini Pro
        "ollama": {"input": 0.0, "output": 0.0},  # Free (local)
        "mock": {"input": 0.0, "output": 0.0},  # Free (local)
    }

    def calculate_message_cost(self, message_id: int) -> float:
        """Calculate the USD cost of a single message based on its token usage."""
        row = self.connection.execute(
            "SELECT prompt_tokens, completion_tokens, provider FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            return 0.0
        prompt_tokens = row["prompt_tokens"] or 0
        completion_tokens = row["completion_tokens"] or 0
        provider = row["provider"] or "mock"

        rates = self.PROVIDER_COST_TABLE.get(provider, {"input": 0, "output": 0})
        cost = (prompt_tokens * rates["input"]) + (completion_tokens * rates["output"])
        return round(cost, 6)

    def get_total_cost(self, session_id: Optional[str] = None) -> dict:
        """Get total token usage and cost for a session or all sessions."""
        if session_id:
            rows = self.connection.execute(
                "SELECT prompt_tokens, completion_tokens, provider FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT prompt_tokens, completion_tokens, provider FROM messages"
            ).fetchall()

        total_prompt = 0
        total_completion = 0
        total_cost = 0.0
        provider_totals = {}

        for r in rows:
            pt = r["prompt_tokens"] or 0
            ct = r["completion_tokens"] or 0
            prov = r["provider"] or "mock"
            total_prompt += pt
            total_completion += ct
            rates = self.PROVIDER_COST_TABLE.get(prov, {"input": 0, "output": 0})
            cost = (pt * rates["input"]) + (ct * rates["output"])
            total_cost += cost
            if prov not in provider_totals:
                provider_totals[prov] = {"prompt": 0, "completion": 0, "cost": 0.0}
            provider_totals[prov]["prompt"] += pt
            provider_totals[prov]["completion"] += ct
            provider_totals[prov]["cost"] += cost

        return {
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_tokens": total_prompt + total_completion,
            "total_cost_usd": round(total_cost, 4),
            "provider_totals": provider_totals,
        }

    # ── Code Snippet Vault ──

    def save_snippet(self, session_id: str, language: str, code: str, description: str = "") -> Optional[int]:
        """Save a code snippet to the vault. Returns snippet ID."""
        now = _now()
        cursor = self.connection.execute(
            "INSERT INTO snippets (session_id, language, code, description, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, language.strip() or "unknown", code, description[:200], now),
        )
        self.connection.commit()
        logger.debug(f"Saved snippet {cursor.lastrowid} ({language})")
        return cursor.lastrowid

    def list_snippets(self, language: Optional[str] = None, limit: int = 50) -> list[dict]:
        """List saved code snippets, optionally filtered by language."""
        if language:
            rows = self.connection.execute(
                "SELECT id, session_id, language, code, description, created_at "
                "FROM snippets WHERE language = ? ORDER BY id DESC LIMIT ?",
                (language, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT id, session_id, language, code, description, created_at "
                "FROM snippets ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_snippet(self, snippet_id: int) -> bool:
        """Delete a snippet by ID."""
        cursor = self.connection.execute(
            "DELETE FROM snippets WHERE id = ?", (snippet_id,)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def get_snippet_languages(self) -> list[str]:
        """Get list of unique snippet languages."""
        rows = self.connection.execute(
            "SELECT DISTINCT language FROM snippets ORDER BY language"
        ).fetchall()
        return [r["language"] for r in rows if r["language"]]

    def search_sessions(self, query: str, limit: int = 20) -> list[Session]:
        """
        Search sessions by name or content (Feature 156).

        Searches both session names and message contents.
        """
        if not query.strip():
            return self.list_sessions(limit=limit)

        search_term = f"%{query.strip()}%"
        rows = self.connection.execute(
            "SELECT DISTINCT s.id, s.name, s.created_at, s.updated_at, s.message_count "
            "FROM sessions s "
            "LEFT JOIN messages m ON m.session_id = s.id "
            "WHERE s.name LIKE ? OR m.content LIKE ? "
            "ORDER BY s.updated_at DESC LIMIT ?",
            (search_term, search_term, limit),
        ).fetchall()
        return [Session(**dict(r)) for r in rows]

    # ── Message Management ──

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
        provider: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> Message:
        """
        Add a message to a session.

        Args:
            session_id: Target session ID
            role: "user", "assistant", or "system"
            content: Message text content
            tokens: Optional token count for tracking
            provider: Optional provider name (ollama, openai, gemini, etc.)
                     for multi-model routing display

        Returns:
            The newly created Message
        """
        now = _now()

        # Auto-name session on FIRST user message (before message_count increment)
        if role == "user":
            self._auto_name_session(session_id, content)

        # Insert message with optional token tracking and cost
        cursor = self.connection.execute(
            "INSERT INTO messages (session_id, role, content, created_at, tokens, provider, prompt_tokens, completion_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, role, content, now, tokens, provider, prompt_tokens, completion_tokens),
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
            provider=provider,
        )
        logger.debug(f"Added message {message.id} to session {session_id} (provider={provider})")
        return message

    def get_messages(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages from a session, oldest first."""
        rows = self.connection.execute(
            "SELECT id, session_id, role, content, created_at, tokens, provider, pinned "
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
        # Get the N most recent messages but return them in chronological order
        rows = self.connection.execute(
            "SELECT * FROM ("            "SELECT id, session_id, role, content, created_at, tokens, provider "
            "FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?"
            ") ORDER BY id ASC",
            (session_id, limit),
        ).fetchall()
        messages = [Message(**dict(r)) for r in rows]
        return [m.to_context_dict() for m in messages]

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count accurately using TokenCounter (tiktoken if available,
        char-based fallback otherwise).
        """
        if not hasattr(self, '_token_counter'):
            self._token_counter = TokenCounter()
        return self._token_counter.count_tokens(text)

    def get_context_by_tokens(
        self,
        session_id: str,
        max_tokens: int = 2000,
    ) -> list[dict]:
        """
        Get recent messages as context, limited by total estimated token count.

        Works backwards from the newest message, accumulating messages until
        the estimated token budget is exhausted. This ensures the context
        fits within the model's context window without hard-truncating mid-message.

        Args:
            session_id: Session to get context from
            max_tokens: Maximum estimated token budget (default 2000)

        Returns:
            List of {"role": str, "content": str} dicts, oldest first within the window
        """
        # Get ALL messages (newest first)
        rows = self.connection.execute(
            "SELECT id, session_id, role, content, created_at, tokens, provider "
            "FROM messages WHERE session_id = ? "
            "ORDER BY id DESC",
            (session_id,),
        ).fetchall()

        if not rows:
            return []

        # Accumulate from newest to oldest until token budget is met
        accumulated_tokens = 0
        selected = []

        for row in rows:
            msg = Message(**dict(row))
            msg_tokens = self._estimate_tokens(msg.content)

            if accumulated_tokens + msg_tokens > max_tokens:
                # This message would exceed the budget — stop here.
                # The message itself is not included (avoid mid-conversation truncation).
                break

            selected.append(msg)
            accumulated_tokens += msg_tokens

        # Reverse to chronological order (oldest first) for LLM context formatting
        selected.reverse()

        logger.debug(
            f"get_context_by_tokens: {len(selected)} messages, "
            f"~{accumulated_tokens} estimated tokens (max {max_tokens})"
        )

        return [m.to_context_dict() for m in selected]

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
        }    # ── Pinned Messages ──

    def pin_message(self, session_id: str, message_id: int) -> Optional[Message]:
        """
        Pin a message so it appears at the top of the session.

        Args:
            session_id: The session the message belongs to
            message_id: The message ID to pin

        Returns:
            Updated Message if successful, None if not found
        """
        cursor = self.connection.execute(
            "UPDATE messages SET pinned = 1 WHERE id = ? AND session_id = ?",
            (message_id, session_id),
        )
        if cursor.rowcount == 0:
            return None
        self.connection.commit()
        logger.debug(f"Pinned message {message_id} in session {session_id}")
        return self.get_message_by_id(session_id, message_id)

    def unpin_message(self, session_id: str, message_id: int) -> Optional[Message]:
        """
        Unpin a message, removing it from the top of the session.

        Args:
            session_id: The session the message belongs to
            message_id: The message ID to unpin

        Returns:
            Updated Message if successful, None if not found
        """
        cursor = self.connection.execute(
            "UPDATE messages SET pinned = 0 WHERE id = ? AND session_id = ?",
            (message_id, session_id),
        )
        if cursor.rowcount == 0:
            return None
        self.connection.commit()
        logger.debug(f"Unpinned message {message_id} in session {session_id}")
        return self.get_message_by_id(session_id, message_id)

    def get_pinned_messages(self, session_id: str) -> list[Message]:
        """
        Get all pinned messages for a session, ordered by id (oldest first).

        Args:
            session_id: The session to get pinned messages from

        Returns:
            List of pinned Message objects
        """
        rows = self.connection.execute(
            "SELECT id, session_id, role, content, created_at, tokens, provider, pinned "
            "FROM messages WHERE session_id = ? AND pinned = 1 "
            "ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        return [Message(**dict(r)) for r in rows]

    # ── Message Editing & Deletion ──

    def get_message_by_id(self, session_id: str, message_id: int) -> Optional[Message]:
        """
        Get a single message by its ID.

        Args:
            session_id: The session the message belongs to
            message_id: The message ID (from messages.id)

        Returns:
            Message if found, None otherwise
        """
        row = self.connection.execute(
            "SELECT id, session_id, role, content, created_at, tokens, provider, pinned "
            "FROM messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
        ).fetchone()

        if row is None:
            return None
        return Message(**dict(row))

    def update_message(
        self,
        session_id: str,
        message_id: int,
        new_content: str,
    ) -> Optional[Message]:
        """
        Update the content of an existing message.

        The session's updated_at timestamp is refreshed.
        Message count is NOT changed (we're editing, not adding).

        Args:
            session_id: The session the message belongs to
            message_id: The message ID to update
            new_content: The new content to replace the old content with

        Returns:
            Updated Message if successful, None if message not found
        """
        if not new_content or not new_content.strip():
            raise AssistantError("Message content cannot be empty")

        now = _now()
        cursor = self.connection.execute(
            "UPDATE messages SET content = ?, created_at = ? "
            "WHERE id = ? AND session_id = ?",
            (new_content, now, message_id, session_id),
        )

        if cursor.rowcount == 0:
            logger.warning(f"Message {message_id} not found in session {session_id}")
            return None

        # Update session timestamp (but NOT message_count — we're editing, not adding)
        self.connection.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        self.connection.commit()

        logger.debug(f"Updated message {message_id} in session {session_id}")
        return self.get_message_by_id(session_id, message_id)

    def delete_message(self, session_id: str, message_id: int) -> Optional[Message]:
        """
        Delete a single message from a session.

        Returns the deleted Message (so the caller can undo the deletion).
        Updates the session's message_count and updated_at.

        Args:
            session_id: The session the message belongs to
            message_id: The message ID to delete

        Returns:
            The deleted Message if found and deleted, None if not found
        """
        # Get the message first (to return for undo)
        msg = self.get_message_by_id(session_id, message_id)
        if msg is None:
            return None

        now = _now()

        # Delete the message
        self.connection.execute(
            "DELETE FROM messages WHERE id = ? AND session_id = ?",
            (message_id, session_id),
        )

        # Update session metadata: decrement message_count, update timestamp
        self.connection.execute(
            "UPDATE sessions SET updated_at = ?, message_count = MAX(0, message_count - 1) "
            "WHERE id = ?",
            (now, session_id),
        )
        self.connection.commit()

        logger.debug(f"Deleted message {message_id} from session {session_id}")
        return msg

    # ── User Preference Memory ──

    def save_preference(self, key: str, value: str) -> None:
        """
        Save a user preference (e.g., user_name, language, theme).

        Stores key-value pairs in the preferences table.
        Values persist across sessions and app restarts.

        Args:
            key: Preference key (e.g., 'user_name', 'language', 'theme')
            value: Preference value (e.g., 'John', 'Vietnamese', 'dark')
        """
        now = _now()
        if not value:
            # Delete preference if value is empty
            self.connection.execute(
                "DELETE FROM preferences WHERE key = ?", (key,)
            )
        else:
            self.connection.execute(
                "INSERT OR REPLACE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now),
            )
        self.connection.commit()
        logger.debug(f"Saved preference: {key}={value!r}")

    def get_preference(self, key: str, default: str = "") -> str:
        """
        Get a saved user preference.

        Args:
            key: Preference key
            default: Default value if key not found

        Returns:
            Preference value string, or default if not found
        """
        row = self.connection.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        if row:
            return row["value"]
        return default

    def get_all_preferences(self) -> dict[str, str]:
        """Get all saved user preferences as a dict."""
        rows = self.connection.execute(
            "SELECT key, value FROM preferences"
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    def delete_preference(self, key: str) -> bool:
        """Delete a preference by key. Returns True if existed."""
        cursor = self.connection.execute(
            "DELETE FROM preferences WHERE key = ?", (key,)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    # ── Forget Memory by Pattern (Feature 19) ──

    def forget_messages_by_pattern(self, session_id: str, pattern: str) -> int:
        """
        Delete all messages in a session whose content contains the given pattern.

        This implements the `/forget` command: users can say
        "/forget tên tôi là..." to delete any message containing "tên tôi là".

        The search is case-insensitive and uses SQL LIKE matching.
        Returns the number of messages deleted.

        Args:
            session_id: The session to search within
            pattern: Text pattern to match (case-insensitive, substring match)

        Returns:
            Number of messages deleted
        """
        if not pattern or not pattern.strip():
            return 0

        search_term = f"%{pattern.strip()}%"
        now = _now()

        # Get count first (for return value)
        count_row = self.connection.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ? AND LOWER(content) LIKE LOWER(?)",
            (session_id, search_term),
        ).fetchone()
        count = count_row[0] if count_row else 0

        if count == 0:
            return 0

        # Delete matching messages
        self.connection.execute(
            "DELETE FROM messages WHERE session_id = ? AND LOWER(content) LIKE LOWER(?)",
            (session_id, search_term),
        )

        # Update session metadata
        self.connection.execute(
            "UPDATE sessions SET updated_at = ?, message_count = MAX(0, message_count - ?) "
            "WHERE id = ?",
            (now, count, session_id),
        )
        self.connection.commit()

        logger.info(f"Forget: deleted {count} messages containing '{pattern}' in session {session_id}")
        return count

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
