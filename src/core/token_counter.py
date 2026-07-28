"""
Token Counter: Accurate token counting using tiktoken with graceful fallback.

Provides:
- Integrated_token_counter: tries tiktoken first, falls back to len//4 estimation
- Model-aware encoding selection (cl100k_base, o200k_base)
- Token truncation utilities
- Message list token counting for context management

Usage:
    counter = TokenCounter()
    tokens = counter.count_tokens("Hello, world!")
    truncated = counter.truncate_to_tokens(long_text, max_tokens=100)
    msg_tokens = counter.count_messages(messages)
"""

import re
from typing import Optional

from src.core import setup_logger

logger = setup_logger("token_counter")

# ── Optional tiktoken import ──
try:
    import tiktoken

    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False
    tiktoken = None  # type: ignore[assignment]
    logger.info("tiktoken not installed, falling back to character-based estimation")


# ── Known model → encoding mappings ──

_MODEL_TO_ENCODING: dict[str, str] = {
    # OpenAI
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-3.5": "cl100k_base",
    # Ollama defaults (estimates)
    "llama3": "cl100k_base",
    "llama3.2": "cl100k_base",
    "llama2": "cl100k_base",
    "mistral": "cl100k_base",
    "mixtral": "cl100k_base",
    "codellama": "cl100k_base",
    # Gemini models
    "gemini": "cl100k_base",  # Rough approximation
    "gemini-2.0-flash": "cl100k_base",
    "gemini-2.0-pro": "cl100k_base",
}

# Cache for loaded encodings
_encoding_cache: dict[str, object] = {}


def _get_encoding(model_name: str):
    """
    Get the tiktoken encoding for a given model name.

    Falls back to cl100k_base for unknown models.
    Returns None if tiktoken is not available.
    """
    if not _HAS_TIKTOKEN:
        return None

    # Normalize model name: strip version/size suffixes for matching
    normalized = model_name.lower().strip()

    # Try exact match first
    if normalized in _MODEL_TO_ENCODING:
        enc_name = _MODEL_TO_ENCODING[normalized]
    else:
        # Try partial match
        matched = False
        for pattern, enc in _MODEL_TO_ENCODING.items():
            if normalized.startswith(pattern):
                enc_name = enc
                matched = True
                break
        if not matched:
            # For Ollama/Gemini models with arbitrary names, default to cl100k_base
            enc_name = "cl100k_base"

    # Cache the encoding object
    if enc_name not in _encoding_cache:
        try:
            _encoding_cache[enc_name] = tiktoken.get_encoding(enc_name)
        except Exception:
            logger.warning(f"Failed to load encoding '{enc_name}', falling back to cl100k_base")
            try:
                _encoding_cache[enc_name] = tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None

    return _encoding_cache.get(enc_name)


def _estimate_chars(text: str) -> int:
    """
    Estimate token count using character-based heuristic.

    Rough formula: 1 token ≈ 4 characters for English/Vietnamese.
    This is intentionally conservative (over-estimates) to avoid
    exceeding context windows.
    """
    if not text:
        return 0
    return max(1, len(text) // 3)  # Slightly more conservative than 4


class TokenCounter:
    """Accurate token counter with tiktoken support and graceful fallback."""

    def __init__(self, model_name: str = ""):
        """
        Initialize token counter.

        Args:
            model_name: Optional model name for encoding selection.
                        If empty, will use cl100k_base as default.
        """
        self.model_name = model_name
        self._encoding = _get_encoding(model_name) if model_name else (
            _get_encoding("cl100k_base") if _HAS_TIKTOKEN else None
        )
        self._using_tiktoken = self._encoding is not None

    @classmethod
    def for_model(cls, model_name: str) -> "TokenCounter":
        """Create a TokenCounter optimized for a specific model."""
        return cls(model_name=model_name)

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in a text string.

        Uses tiktoken if available and encoding was loaded, otherwise falls back
        to character-based estimation.

        Args:
            text: The text to count tokens for

        Returns:
            Estimated/actual token count (always >= 0)
        """
        if not text:
            return 0

        if self._using_tiktoken and self._encoding is not None:
            try:
                return len(self._encoding.encode(text, disallowed_special=()))
            except Exception as e:
                logger.debug(f"tiktoken encoding failed, falling back: {e}")
                return _estimate_chars(text)

        return _estimate_chars(text)

    def count_messages(self, messages: list[dict]) -> int:
        """
        Count total tokens in a list of messages.

        Each message contributes: role tokens + content tokens + overhead (~4 tokens per message)

        Args:
            messages: List of {"role": str, "content": str} dicts

        Returns:
            Total estimated/actual token count
        """
        total = 0
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Count role + content tokens
            total += self.count_tokens(role) + self.count_tokens(content)
            # Per-message overhead (formatting, etc.)
            total += 4
        return total

    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within a token budget.

        Preserves the beginning of the text (important for context).
        If the text fits within the budget, returns it unchanged.

        Args:
            text: The text to potentially truncate
            max_tokens: Maximum allowed tokens

        Returns:
            Truncated text (or original if within budget)
        """
        if not text or max_tokens <= 0:
            return ""

        count = self.count_tokens(text)
        if count <= max_tokens:
            return text

        # Truncate by approximating: reduce character count proportionally
        # Be conservative: aim for 90% of the budget
        target_chars = int(len(text) * (max_tokens * 0.9) / max(count, 1))

        if self._using_tiktoken and self._encoding is not None:
            # Use tiktoken for precise truncation
            try:
                tokens = self._encoding.encode(text, disallowed_special=())
                truncated_tokens = tokens[:max_tokens]
                return self._encoding.decode(truncated_tokens)
            except Exception:
                pass

        # Fallback: truncate by characters
        truncated = text[:target_chars]
        # Ensure we don't end mid-word
        last_space = truncated.rfind(" ")
        if last_space > len(truncated) // 2:
            truncated = truncated[:last_space]
        return truncated.strip() + " [...]"

    def truncate_messages(
        self,
        messages: list[dict],
        max_tokens: int,
        preserve_last: int = 1,
    ) -> list[dict]:
        """
        Truncate message list to fit within a token budget.

        Works backwards from the newest message, preserving context.
        The system prompt (if any) is always preserved.

        Args:
            messages: List of {"role": str, "content": str} dicts
            max_tokens: Maximum allowed total tokens
            preserve_last: Number of newest messages to always keep

        Returns:
            Truncated message list (oldest first)
        """
        if not messages:
            return []

        # Separate system messages (always preserved)
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        if not non_system:
            return messages

        # Always keep the N newest non-system messages
        if preserve_last > 0:
            guaranteed = non_system[-preserve_last:]
            candidates = non_system[:-preserve_last]
        else:
            guaranteed = []
            candidates = list(non_system)

        # Count tokens for guaranteed messages + system messages
        guaranteed_tokens = self.count_messages(guaranteed)
        system_tokens = self.count_messages(system_msgs)
        budget = max_tokens - guaranteed_tokens - system_tokens

        # Accumulate candidates from newest to oldest
        selected = []
        for msg in reversed(candidates):
            msg_tokens = self.count_tokens(msg.get("content", ""))
            msg_tokens += self.count_tokens(msg.get("role", "user")) + 4
            if budget - msg_tokens >= 0:
                selected.insert(0, msg)
                budget -= msg_tokens
            else:
                break

        # Reassemble
        result = list(system_msgs) + selected + guaranteed
        return result

    def get_usage_report(self, text: str) -> dict:
        """
        Get a detailed token usage report for a text.

        Returns dict with counts and metadata useful for logging/debugging.
        """
        char_count = len(text)
        token_count = self.count_tokens(text)
        return {
            "characters": char_count,
            "tokens": token_count,
            "ratio": round(char_count / max(token_count, 1), 2),
            "method": "tiktoken" if self._using_tiktoken else "estimation",
            "model": self.model_name or "default",
        }

    def __repr__(self) -> str:
        method = "tiktoken" if self._using_tiktoken else "chars/3 estimation"
        return f"TokenCounter(model={self.model_name!r}, method={method})"
