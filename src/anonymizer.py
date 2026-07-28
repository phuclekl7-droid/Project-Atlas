"""
PII Anonymizer (Feature 71): Masks personally identifiable information
before sending messages to external (non-local) LLM APIs.

Supports masking of:
  - Email addresses
  - Phone numbers (Vietnamese + international)
  - Credit card numbers
  - Social Security Numbers / CMND / CCCD
  - IP addresses
  - Passport numbers

All masking is reversible (the original text is preserved in session state)
and only applied when the provider is NOT local (ollama/mock).
"""

import re
from typing import Optional

from src.core import setup_logger

logger = setup_logger("anonymizer")

# Regex patterns for various PII types
_PII_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    "phone_vn": re.compile(r'(?:\+84|0)[1-9][0-9]{8,9}'),
    "phone_intl": re.compile(r'\+\d{1,3}[-\s]?\d{1,14}(?:[-\s]?\d{1,13})?'),
    "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    "ssn": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
    "cccd": re.compile(r'\b(?:0[0-9]{11}|[1-9][0-9]{11})\b'),  # Vietnamese ID (12 digits)
    "ip": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "passport": re.compile(r'\b[A-Z]{1,2}[0-9]{6,9}\b'),
}

# Masking templates
_MASKS: dict[str, str] = {
    "email": "[EMAIL_REDACTED]",
    "phone_vn": "[PHONE_REDACTED]",
    "phone_intl": "[PHONE_REDACTED]",
    "credit_card": "[CC_REDACTED]",
    "ssn": "[SSN_REDACTED]",
    "cccd": "[ID_REDACTED]",
    "ip": "[IP_REDACTED]",
    "passport": "[PASSPORT_REDACTED]",
}

# Labels for display
_PII_LABELS: dict[str, str] = {
    "email": "Email",
    "phone_vn": "Số điện thoại (VN)",
    "phone_intl": "Số điện thoại (QT)",
    "credit_card": "Thẻ tín dụng",
    "ssn": "SSN",
    "cccd": "CCCD/CMND",
    "ip": "Địa chỉ IP",
    "passport": "Passport",
}


def mask_pii(text: str, enabled_types: Optional[set[str]] = None) -> str:
    """
    Mask all PII in the given text using regex patterns.

    Args:
        text: The input text to mask
        enabled_types: Optional set of PII types to mask.
                      If None, all types are masked.

    Returns:
        Text with PII replaced by mask placeholders

    Example:
        >>> mask_pii("Email me at test@example.com or call 0123456789")
        'Email me at [EMAIL_REDACTED] or call [PHONE_REDACTED]'
    """
    if not text:
        return text

    masked = text
    count_by_type: dict[str, int] = {}

    # Apply masks for all enabled (or all) types
    for pii_type, pattern in _PII_PATTERNS.items():
        if enabled_types is not None and pii_type not in enabled_types:
            continue
        mask = _MASKS.get(pii_type, f"[{pii_type.upper()}_REDACTED]")
        masked, count = pattern.subn(mask, masked)
        if count > 0:
            count_by_type[pii_type] = count

    if count_by_type:
        details = ", ".join(
            f"{_PII_LABELS.get(t, t)}: {c}" for t, c in count_by_type.items()
        )
        logger.info(f"Masked PII: {details}")

    return masked


def detect_pii(text: str) -> dict[str, int]:
    """
    Detect PII in text without masking. Returns counts per type.

    Args:
        text: Input text to scan

    Returns:
        Dict of {pii_type: count} for detected PII

    Example:
        >>> detect_pii("Call 0123456789 or email a@b.com")
        {'phone_vn': 1, 'email': 1}
    """
    if not text:
        return {}

    detected: dict[str, int] = {}
    for pii_type, pattern in _PII_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            detected[pii_type] = len(matches)
    return detected


def should_mask(provider: str) -> bool:
    """
    Determine if masking should be applied based on the provider.

    Only masks when sending to external/cloud providers.
    Local providers (ollama, mock) don't need masking.

    Args:
        provider: The model provider name (ollama, openai, gemini, mock)

    Returns:
        True if the provider is external (data leaves the machine)
    """
    return provider not in ("ollama", "mock", "llama")
