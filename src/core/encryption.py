"""
Encryption module (Feature 73): AES-256 encrypted storage for API keys.

Uses the `cryptography` library (specifically Fernet, which is AES-128-CBC
with HMAC-SHA256, giving ~256-bit effective security).

If `cryptography` is not installed, falls back to a simple base64 obfuscation
(with a warning logged) so the app doesn't crash on import.

Usage:
    cipher = Encryptor(key_file="data/.secret.key")
    encrypted = cipher.encrypt("sk-...")
    plain = cipher.decrypt(encrypted)
"""

import base64
import json
import os
import warnings
from pathlib import Path
from typing import Optional

from src.core import setup_logger

logger = setup_logger("encryption")

# Try to import cryptography; fall back to simple obfuscation
_HAS_CRYPTOGRAPHY = False
try:
    from cryptography.fernet import Fernet, InvalidToken

    _HAS_CRYPTOGRAPHY = True
except ImportError:
    Fernet = None  # type: ignore
    InvalidToken = None  # type: ignore


class Encryptor:
    """AES-256 encrypted storage for sensitive configuration values.

    The encryption key is stored in a local file (default: data/.secret.key).
    If the file doesn't exist, a new key is generated automatically.

    When `cryptography` is unavailable, falls back to base64 obfuscation
    (NOT secure, but prevents casual shoulder-surfing).
    """

    def __init__(self, key_file: str = "data/.secret.key"):
        self.key_file = str(key_file)

        if _HAS_CRYPTOGRAPHY and Fernet is not None:
            self._fernet = self._load_or_create_fernet()
            self._mode = "aes256"
            logger.info(f"Encryption initialized (AES-256): {self.key_file}")
        else:
            self._mode = "obfuscate"
            warnings.warn(
                "cryptography library not installed. "
                "API keys will use BASE64 obfuscation (NOT secure). "
                "Install with: pip install cryptography",
                RuntimeWarning,
            )
            logger.warning("cryptography not installed — using base64 obfuscation only")

    def _load_or_create_fernet(self) -> "Fernet":
        """Load existing key or generate a new one."""
        key_path = Path(self.key_file)
        key_path.parent.mkdir(parents=True, exist_ok=True)

        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()  # type: ignore
            key_path.write_bytes(key)
            key_path.chmod(0o600)  # Only owner can read
            logger.info(f"Generated new encryption key: {self.key_file}")

        return Fernet(key)  # type: ignore

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value.

        Args:
            plaintext: The plain text value to encrypt

        Returns:
            Base64-encoded encrypted string, prefixed with mode indicator
        """
        if not plaintext:
            return ""

        if self._mode == "aes256" and self._fernet is not None:
            token = self._fernet.encrypt(plaintext.encode("utf-8"))
            return f"$aes${token.decode('utf-8')}"
        else:
            # Fallback: base64 encode (NOT secure)
            encoded = base64.b64encode(plaintext.encode("utf-8")).decode("utf-8")
            return f"$b64${encoded}"

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a string value.

        Args:
            encrypted: The encrypted string (with mode indicator prefix)

        Returns:
            Decrypted plain text, or empty string on failure
        """
        if not encrypted:
            return ""

        try:
            if encrypted.startswith("$aes$"):
                if self._mode != "aes256" or self._fernet is None:
                    logger.error("Cannot decrypt AES data — cryptography not available")
                    return ""
                token = encrypted[5:]
                return self._fernet.decrypt(token.encode("utf-8")).decode("utf-8")

            elif encrypted.startswith("$b64$"):
                encoded = encrypted[5:]
                return base64.b64decode(encoded).decode("utf-8")

            else:
                # Plain text (not encrypted) — return as-is
                return encrypted
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return ""

    def encrypt_file(self, file_path: str) -> bool:
        """Encrypt the contents of a file in-place.

        Reads the file, encrypts its content, and writes it back
        with a `.encrypted` extension indicator.

        Args:
            file_path: Path to the file to encrypt

        Returns:
            True if successful
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return False

        try:
            content = path.read_text(encoding="utf-8")
            encrypted = self.encrypt(content)
            # Write encrypted content back with marker
            path.write_text(encrypted, encoding="utf-8")
            logger.info(f"Encrypted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to encrypt file {file_path}: {e}")
            return False

    def decrypt_file(self, file_path: str) -> Optional[str]:
        """Decrypt a file that was encrypted with encrypt_file().

        Args:
            file_path: Path to the encrypted file

        Returns:
            Decrypted content as string, or None on failure
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        try:
            encrypted = path.read_text(encoding="utf-8").strip()
            return self.decrypt(encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt file {file_path}: {e}")
            return None
