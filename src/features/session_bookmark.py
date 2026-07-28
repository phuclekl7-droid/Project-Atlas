"""
Session Bookmark (Feature 166: Favorite / Pinned Sessions)

Allows users to star/bookmark important chat sessions so they appear
at the top of the sidebar session list.

Uses SQLite-backed preferences via Memory.save_preference() for persistence
across app restarts.

Usage:
    bookmark = SessionBookmark(memory)
    bookmark.toggle(session_id)          # Star/unstar
    starred = bookmark.get_starred()      # List of starred session IDs
    is_starred = bookmark.is_starred(session_id)
    sort_key = bookmark.sort_key(session)  # For sorting sessions
"""

from typing import Optional

# Preference key prefix stored in Memory
_PREF_KEY_PREFIX = "bookmark_session_"


class SessionBookmark:
    """
    Manages bookmarked (favorited) sessions.

    Uses Memory.save_preference/get_preference for persistence.
    Bookmark state is stored as "bookmark_session_{id}" → "1" or "0".
    """

    def __init__(self, memory):
        """
        Args:
            memory: Memory instance (must have save_preference/get_preference)
        """
        self._memory = memory

    def _pref_key(self, session_id: str) -> str:
        return f"{_PREF_KEY_PREFIX}{session_id}"

    def toggle(self, session_id: str) -> bool:
        """
        Toggle the bookmark state for a session.

        Args:
            session_id: The session ID to toggle

        Returns:
            True if session is now bookmarked, False if unbookmarked
        """
        if not session_id:
            return False
        currently = self.is_starred(session_id)
        new_value = "0" if currently else "1"
        self._memory.save_preference(self._pref_key(session_id), new_value)
        return not currently

    def star(self, session_id: str) -> None:
        """Bookmark a session."""
        if session_id:
            self._memory.save_preference(self._pref_key(session_id), "1")

    def unstar(self, session_id: str) -> None:
        """Unbookmark a session."""
        if session_id:
            self._memory.save_preference(self._pref_key(session_id), "0")

    def is_starred(self, session_id: str) -> bool:
        """Check if a session is bookmarked."""
        if not session_id:
            return False
        val = self._memory.get_preference(self._pref_key(session_id), "0")
        return val == "1"

    def get_starred(self, session_ids: Optional[list[str]] = None) -> list[str]:
        """
        Get all bookmarked session IDs.

        Args:
            session_ids: Optional list to filter against (only return IDs in this list)

        Returns:
            List of bookmarked session IDs
        """
        if not self._memory:
            return []

        all_prefs = self._memory.get_all_preferences()
        starred = []
        for key, value in all_prefs.items():
            if key.startswith(_PREF_KEY_PREFIX) and value == "1":
                sid = key[len(_PREF_KEY_PREFIX):]
                if session_ids is None or sid in session_ids:
                    starred.append(sid)
        return starred

    def sort_key(self, session) -> tuple:
        """
        Sort key for session lists: starred sessions first, then by updated_at.

        Usage:
            sessions.sort(key=lambda s: bookmark.sort_key(s))
        """
        is_starred = 0 if self.is_starred(session.id) else 1
        updated = getattr(session, "updated_at", "") or ""
        return (is_starred, updated or "")

    def clear_all(self) -> int:
        """Unstar all bookmarked sessions. Returns count cleared."""
        starred = self.get_starred()
        for sid in starred:
            self._memory.save_preference(self._pref_key(sid), "0")
        return len(starred)
