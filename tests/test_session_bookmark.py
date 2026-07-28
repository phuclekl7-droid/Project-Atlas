"""
Unit tests for Session Bookmark (Favorite Sessions).

Tests:
- SessionBookmark dataclass / init
- toggle() flip-flop logic
- star() and unstar()
- is_starred() checks
- get_starred() returns correct IDs
- sort_key() puts starred first
- clear_all() removes all bookmarks
- empty/None inputs handled gracefully
"""

from unittest.mock import MagicMock, patch

import pytest

from src.features.session_bookmark import SessionBookmark


class MockMemory:
    """Minimal mock for Memory that stores preferences in a dict."""
    def __init__(self):
        self._prefs = {}

    def save_preference(self, key, value):
        self._prefs[key] = value

    def get_preference(self, key, default=""):
        return self._prefs.get(key, default)

    def get_all_preferences(self):
        return dict(self._prefs)


class MockSession:
    def __init__(self, id="s1", name="Test", updated_at="2024-01-01"):
        self.id = id
        self.name = name
        self.updated_at = updated_at


class TestSessionBookmark:
    @pytest.fixture
    def memory(self):
        return MockMemory()

    @pytest.fixture
    def bookmark(self, memory):
        return SessionBookmark(memory)

    def test_init(self, bookmark):
        """Init should work without error."""
        assert bookmark is not None

    def test_toggle_off_to_on(self, bookmark):
        """Toggle should go from False to True."""
        result = bookmark.toggle("session_123")
        assert result is True  # Now bookmarked

    def test_toggle_on_to_off(self, bookmark):
        """Toggle should go from True to False."""
        bookmark.star("session_123")
        result = bookmark.toggle("session_123")
        assert result is False  # Now unbookmarked

    def test_star(self, bookmark):
        """star() should set bookmark."""
        bookmark.star("session_123")
        assert bookmark.is_starred("session_123") is True

    def test_unstar(self, bookmark):
        """unstar() should remove bookmark."""
        bookmark.star("session_123")
        bookmark.unstar("session_123")
        assert bookmark.is_starred("session_123") is False

    def test_is_starred_default_false(self, bookmark):
        """Unbookmarked session should return False."""
        assert bookmark.is_starred("nonexistent") is False

    def test_is_starred_empty_id(self, bookmark):
        """Empty session ID should return False."""
        assert bookmark.is_starred("") is False

    def test_get_starred_empty(self, bookmark):
        """No starred sessions should return empty list."""
        starred = bookmark.get_starred()
        assert starred == []

    def test_get_starred_with_ids(self, bookmark):
        """get_starred with session IDs list should filter."""
        bookmark.star("s1")
        bookmark.star("s2")
        bookmark.star("s3")
        starred = bookmark.get_starred(session_ids=["s1", "s3"])
        assert "s1" in starred
        assert "s2" not in starred  # s2 is starred but not in filter list
        assert "s3" in starred

    def test_get_starred_all(self, bookmark):
        """get_starred() without filter should return all."""
        bookmark.star("s1")
        bookmark.star("s2")
        starred = bookmark.get_starred()
        assert len(starred) == 2
        assert "s1" in starred
        assert "s2" in starred

    def test_sort_key_starred_first(self, bookmark):
        """Starred sessions should have lower sort key (0 vs 1)."""
        s_starred = MockSession(id="starred")
        s_normal = MockSession(id="normal")
        bookmark.star("starred")

        key_starred = bookmark.sort_key(s_starred)
        key_normal = bookmark.sort_key(s_normal)
        assert key_starred < key_normal

    def test_sort_key_ordering(self, bookmark):
        """Sessions should sort: starred first, then by updated_at."""
        s1 = MockSession(id="s1", updated_at="2024-01-01")
        s2 = MockSession(id="s2", updated_at="2024-01-02")
        bookmark.star("s2")

        sessions = [s1, s2]
        sessions.sort(key=lambda s: bookmark.sort_key(s))
        assert sessions[0].id == "s2"  # Starred first
        assert sessions[1].id == "s1"  # Normal second

    def test_clear_all(self, bookmark):
        """clear_all() should remove all bookmarks and return count."""
        bookmark.star("s1")
        bookmark.star("s2")
        bookmark.star("s3")
        count = bookmark.clear_all()
        assert count == 3
        assert bookmark.is_starred("s1") is False
        assert bookmark.is_starred("s2") is False
        assert bookmark.get_starred() == []

    def test_toggle_empty_id(self, bookmark):
        """Toggling empty ID should return False."""
        assert bookmark.toggle("") is False

    def test_toggle_none_id(self, bookmark):
        """Toggling None ID should return False."""
        assert bookmark.toggle(None) is False

    def test_starred_list_empty_memory(self):
        """get_starred() with empty preference list should return []."""
        mem = MagicMock()
        mem.get_all_preferences.return_value = {}
        bm = SessionBookmark(mem)
        assert bm.get_starred() == []

    def test_starred_list_filters_non_bookmark_prefs(self, memory):
        """get_starred() should ignore non-bookmark preferences."""
        memory.save_preference("user_name", "Alice")
        memory.save_preference("theme", "dark")
        bm = SessionBookmark(memory)
        assert bm.get_starred() == []
