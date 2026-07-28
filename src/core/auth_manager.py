"""
User Authentication & JWT Manager (Feature #75).
Handles user registration, login, and session management for multi-user support.

Uses HMAC-based tokens with hashlib (no PyJWT dependency needed).
Passwords are hashed with SHA-256 + salt.

Usage:
    auth = AuthManager()
    auth.register_user("admin", "secret123", role="admin")
    token = auth.login("admin", "secret123")
    user = auth.verify_token(token)  # -> {"username": "admin", "role": "admin"}
    auth.logout(token)
"""

import hmac
import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.core import setup_logger

logger = setup_logger("auth")


@dataclass
class User:
    """Authenticated user data."""
    username: str
    role: str = "user"  # admin, user, guest
    created_at: float = 0.0
    last_login: float = 0.0


@dataclass
class Session:
    """Active user session."""
    token: str
    username: str
    role: str
    created_at: float
    expires_at: float
    ip_address: str = ""


class AuthManager:
    """
    Manages user authentication with HMAC-signed tokens.

    Thread-safe for Streamlit multi-user scenarios.
    Stores users in SQLite database.

    Usage:
        auth = AuthManager("data/auth.db")
        auth.register_user("admin", "my_password", role="admin")
        token = auth.login("admin", "my_password")
        user = auth.verify_token(token)
        auth.logout(token)
    """

    def __init__(self, db_path: str = "data/auth.db"):
        self.db_path = db_path
        self._secret = self._load_or_create_secret()
        self._lock = threading.RLock()
        self._token_ttl = 86400  # 24 hours
        self._sessions: dict[str, Session] = {}  # In-memory session cache

        # Initialize database
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _load_or_create_secret(self) -> bytes:
        """Load or generate the HMAC secret key."""
        secret_file = Path(self.db_path).parent / ".auth_secret"
        if secret_file.exists():
            try:
                return secret_file.read_bytes()
            except Exception:
                pass
        # Generate new secret
        secret = os.urandom(32)
        try:
            secret_file.write_bytes(secret)
            logger.info("Generated new auth secret key")
        except Exception as e:
            logger.warning(f"Cannot save auth secret: {e}")
        return secret

    def _init_db(self) -> None:
        """Initialize the users table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        created_at REAL NOT NULL,
                        last_login REAL DEFAULT 0
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to init auth DB: {e}")

    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash a password with salt. Returns (hash, salt)."""
        if salt is None:
            salt = hashlib.sha256(os.urandom(32)).hexdigest()[:16]
        hash_val = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return hash_val, salt

    def _generate_token(self, username: str, role: str) -> str:
        """Generate an HMAC-signed token."""
        payload = json.dumps({
            "username": username,
            "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + self._token_ttl,
        }, separators=(",", ":"))
        # HMAC sign
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
        # Encode payload as base64-url-safe-ish
        encoded = payload.encode("utf-8").hex()
        return f"{encoded}.{signature}"

    def _decode_token(self, token: str) -> Optional[dict]:
        """Decode and verify an HMAC-signed token."""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None
            encoded, signature = parts
            payload_bytes = bytes.fromhex(encoded)
            payload = payload_bytes.decode("utf-8")

            # Verify signature
            expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None

            data = json.loads(payload)
            # Check expiration
            if data.get("exp", 0) < time.time():
                logger.debug(f"Token expired for {data.get('username', 'unknown')}")
                return None

            return data
        except Exception as e:
            logger.debug(f"Token decode failed: {e}")
            return None

    # ── Public API ──

    def register_user(self, username: str, password: str, role: str = "user") -> tuple[bool, str]:
        """
        Register a new user.

        Returns:
            (success, message)
        """
        if not username or len(username) < 2:
            return False, "Username must be at least 2 characters"
        if not password or len(password) < 4:
            return False, "Password must be at least 4 characters"
        if role not in ("admin", "user", "guest"):
            return False, f"Invalid role: {role}"

        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    # Check if exists
                    existing = conn.execute(
                        "SELECT username FROM users WHERE username = ?", (username,)
                    ).fetchone()
                    if existing:
                        return False, f"User '{username}' already exists"

                    pw_hash, salt = self._hash_password(password)
                    conn.execute(
                        "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
                        (username, pw_hash, salt, role, time.time()),
                    )
                    conn.commit()
                    logger.info(f"Registered user '{username}' (role={role})")
                    return True, f"User '{username}' registered successfully"

            except Exception as e:
                logger.error(f"Registration failed: {e}")
                return False, f"Registration failed: {e}"

    def login(self, username: str, password: str, ip_address: str = "") -> Optional[str]:
        """
        Authenticate a user and return a session token.

        Returns:
            Token string if successful, None if failed
        """
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    row = conn.execute(
                        "SELECT username, password_hash, salt, role FROM users WHERE username = ?",
                        (username,),
                    ).fetchone()
                    if not row:
                        logger.warning(f"Login failed: unknown user '{username}'")
                        return None

                    db_user, db_hash, db_salt, db_role = row
                    pw_hash, _ = self._hash_password(password, db_salt)
                    if pw_hash != db_hash:
                        logger.warning(f"Login failed: wrong password for '{username}'")
                        return None

                    # Update last login
                    conn.execute(
                        "UPDATE users SET last_login = ? WHERE username = ?",
                        (time.time(), username),
                    )
                    conn.commit()

                    # Generate token
                    token = self._generate_token(username, db_role)
                    session = Session(
                        token=token,
                        username=username,
                        role=db_role,
                        created_at=time.time(),
                        expires_at=time.time() + self._token_ttl,
                        ip_address=ip_address,
                    )
                    self._sessions[token] = session
                    logger.info(f"User '{username}' logged in (role={db_role})")
                    return token

            except Exception as e:
                logger.error(f"Login error: {e}")
                return None

    def verify_token(self, token: str) -> Optional[User]:
        """
        Verify a session token and return user info.

        Returns:
            User if token is valid, None if invalid/expired
        """
        if not token:
            return None

        # Check in-memory cache first
        session = self._sessions.get(token)
        if session:
            if session.expires_at > time.time():
                return User(username=session.username, role=session.role)
            else:
                del self._sessions[token]
                return None

        # Decode and verify
        data = self._decode_token(token)
        if data is None:
            return None

        return User(username=data["username"], role=data.get("role", "user"))

    def logout(self, token: str) -> bool:
        """Invalidate a session token."""
        with self._lock:
            if token in self._sessions:
                del self._sessions[token]
                logger.debug(f"User logged out (token invalidated)")
                return True
            return False

    def list_users(self) -> list[dict]:
        """List all registered users (safe, no passwords)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT username, role, created_at, last_login FROM users ORDER BY username"
                ).fetchall()
                return [
                    {
                        "username": r[0],
                        "role": r[1],
                        "created_at": r[2],
                        "last_login": r[3],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

    def delete_user(self, username: str) -> bool:
        """Delete a user account."""
        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("DELETE FROM users WHERE username = ?", (username,))
                    conn.commit()
                    # Invalidate any active sessions
                    expired = [t for t, s in self._sessions.items() if s.username == username]
                    for t in expired:
                        del self._sessions[t]
                    return True
            except Exception as e:
                logger.error(f"Failed to delete user '{username}': {e}")
                return False

    def get_stats(self) -> dict:
        """Get authentication statistics."""
        users = self.list_users()
        active_sessions = len([
            s for s in self._sessions.values() if s.expires_at > time.time()
        ])
        return {
            "total_users": len(users),
            "active_sessions": active_sessions,
            "database": self.db_path,
        }
