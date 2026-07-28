"""
Tests for Feature #75: User Authentication (JWT).
"""

import time
from pathlib import Path

import pytest

from src.core.auth_manager import AuthManager, User


@pytest.fixture
def auth(tmp_path):
    """Create an AuthManager with a temp database."""
    db_path = str(tmp_path / "test_auth.db")
    manager = AuthManager(db_path=db_path)
    yield manager
    # Cleanup
    manager._sessions.clear()
    secret_file = Path(db_path).parent / ".auth_secret"
    if secret_file.exists():
        secret_file.unlink(missing_ok=True)


class TestAuthManager:
    """Tests for the AuthManager class."""

    def test_register_user(self, auth):
        success, msg = auth.register_user("testuser", "password123")
        assert success
        assert "registered" in msg.lower()

    def test_register_duplicate_user(self, auth):
        auth.register_user("testuser", "password123")
        success, msg = auth.register_user("testuser", "anotherpass")
        assert not success
        assert "already exists" in msg.lower()

    def test_register_short_username(self, auth):
        success, msg = auth.register_user("x", "password123")
        assert not success

    def test_register_short_password(self, auth):
        success, msg = auth.register_user("testuser", "ab")
        assert not success

    def test_login_success(self, auth):
        auth.register_user("testuser", "password123")
        token = auth.login("testuser", "password123")
        assert token is not None
        assert len(token) > 10

    def test_login_wrong_password(self, auth):
        auth.register_user("testuser", "password123")
        token = auth.login("testuser", "wrongpassword")
        assert token is None

    def test_login_unknown_user(self, auth):
        token = auth.login("nonexistent", "password")
        assert token is None

    def test_verify_token_valid(self, auth):
        auth.register_user("testuser", "password123")
        token = auth.login("testuser", "password123")
        user = auth.verify_token(token)
        assert user is not None
        assert user.username == "testuser"
        assert user.role == "user"

    def test_verify_token_invalid(self, auth):
        user = auth.verify_token("invalid.token.here")
        assert user is None

    def test_verify_token_empty(self, auth):
        user = auth.verify_token("")
        assert user is None

    def test_logout(self, auth):
        auth.register_user("testuser", "password123")
        token = auth.login("testuser", "password123")
        assert auth.logout(token)
        assert auth.verify_token(token) is None

    def test_register_admin_role(self, auth):
        success, _ = auth.register_user("admin", "adminpass", role="admin")
        assert success
        token = auth.login("admin", "adminpass")
        user = auth.verify_token(token)
        assert user is not None
        assert user.role == "admin"

    def test_list_users(self, auth):
        auth.register_user("user1", "pass1")
        auth.register_user("user2", "pass2")
        users = auth.list_users()
        assert len(users) >= 2
        usernames = [u["username"] for u in users]
        assert "user1" in usernames
        assert "user2" in usernames

    def test_delete_user(self, auth):
        auth.register_user("todelete", "password")
        assert auth.delete_user("todelete")
        users = auth.list_users()
        usernames = [u["username"] for u in users]
        assert "todelete" not in usernames

    def test_get_stats(self, auth):
        auth.register_user("user1", "pass1")
        stats = auth.get_stats()
        assert stats["total_users"] >= 1
        assert stats["active_sessions"] >= 0
