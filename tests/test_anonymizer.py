"""
Unit tests for the PII Anonymizer module (Feature 71).

Tests mask_pii(), detect_pii(), and should_mask() functions.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.anonymizer import mask_pii, detect_pii, should_mask


class TestMaskPII:
    """Tests for mask_pii() function."""

    def test_mask_email(self):
        result = mask_pii("Contact me at user@example.com please")
        assert "[EMAIL_REDACTED]" in result
        assert "user@example.com" not in result

    def test_mask_phone_vn(self):
        result = mask_pii("Call 0123456789 now!")
        assert "[PHONE_REDACTED]" in result
        assert "0123456789" not in result

    def test_mask_phone_vn_with_country_code(self):
        result = mask_pii("Call +84912345678")
        assert "[PHONE_REDACTED]" in result
        assert "+84912345678" not in result

    def test_mask_credit_card(self):
        result = mask_pii("Card: 4111-1111-1111-1111")
        assert "[CC_REDACTED]" in result

    def test_mask_ip(self):
        result = mask_pii("Server IP: 192.168.1.1")
        assert "[IP_REDACTED]" in result

    def test_empty_string(self):
        assert mask_pii("") == ""
        assert mask_pii(None) is None

    def test_no_pii(self):
        text = "Hello, how are you today?"
        assert mask_pii(text) == text

    def test_multiple_pii_types(self):
        text = "Email: a@b.com, Phone: 0123456789"
        result = mask_pii(text)
        assert "[EMAIL_REDACTED]" in result
        assert "[PHONE_REDACTED]" in result

    def test_enabled_types_filter(self):
        text = "Email: a@b.com, Phone: 0123456789"
        result = mask_pii(text, enabled_types={"email"})
        assert "[EMAIL_REDACTED]" in result
        assert "0123456789" in result  # Phone should NOT be masked


class TestDetectPII:
    """Tests for detect_pii() function."""

    def test_detect_email(self):
        result = detect_pii("a@b.com")
        assert result.get("email") == 1

    def test_detect_phone(self):
        result = detect_pii("Call 0123456789")
        assert result.get("phone_vn") == 1

    def test_detect_multiple(self):
        result = detect_pii("Email: a@b.com, Phone: 0123456789, IP: 10.0.0.1")
        assert result.get("email") == 1
        assert result.get("phone_vn") == 1
        assert result.get("ip") == 1

    def test_empty_string(self):
        assert detect_pii("") == {}
        assert detect_pii(None) == {}


class TestShouldMask:
    """Tests for should_mask() function."""

    def test_should_mask_openai(self):
        assert should_mask("openai") is True

    def test_should_mask_gemini(self):
        assert should_mask("gemini") is True

    def test_should_not_mask_ollama(self):
        assert should_mask("ollama") is False

    def test_should_not_mask_mock(self):
        assert should_mask("mock") is False
