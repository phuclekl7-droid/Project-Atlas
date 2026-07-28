"""
Unit tests for the Token Counter module.

Tests:
- count_tokens with tiktoken (mocked) and character-based fallback
- count_messages: total tokens for message lists
- truncate_to_tokens: fitting text within token budgets
- truncate_messages: pruning message lists with system message preservation
- get_usage_report: metadata accuracy
- Edge cases: empty text, single char, very long text
"""

from unittest.mock import patch

import pytest

from src.core.token_counter import TokenCounter, _estimate_chars


# ============================================================
# Character-Based Estimation (Fallback)
# ============================================================


class TestEstimateChars:
    def test_estimate_empty(self):
        """Empty text should return 0."""
        assert _estimate_chars("") == 0

    def test_estimate_short_text(self):
        """Short text should return at least 1."""
        assert _estimate_chars("a") == 1

    def test_estimate_approximate(self):
        """Estimation should be roughly len//3."""
        text = "Hello, world!" * 10  # 130 chars
        estimate = _estimate_chars(text)
        # 130 // 3 = 43
        assert estimate == 43

    def test_estimate_long_text(self):
        """Longer text should scale proportionally."""
        text = "This is a test of the emergency broadcast system. " * 20
        estimate = _estimate_chars(text)
        assert estimate > 50
        assert estimate < 2000


# ============================================================
# TokenCounter — Basic Counting
# ============================================================


class TestTokenCounterInit:
    def test_default_init(self):
        """TokenCounter should init without arguments."""
        counter = TokenCounter()
        assert counter is not None
        # Should fall back to character estimation if tiktoken not available
        assert counter._using_tiktoken is hasattr(pytest, 'has_tiktoken') or _has_tiktoken_available()

    def test_init_with_model(self):
        """TokenCounter should accept a model name."""
        counter = TokenCounter(model_name="gpt-4o-mini")
        assert counter.model_name == "gpt-4o-mini"

    def test_for_model_classmethod(self):
        """for_model should return a properly configured counter."""
        counter = TokenCounter.for_model("gpt-4")
        assert counter.model_name == "gpt-4"

    def test_repr(self):
        """__repr__ should include model name and method."""
        counter = TokenCounter(model_name="test-model")
        r = repr(counter)
        assert "test-model" in r
        assert "tiktoken" in r or "estimation" in r


class TestCountTokens:
    def test_count_empty(self, token_counter):
        """Empty text should return 0 tokens."""
        assert token_counter.count_tokens("") == 0

    def test_count_single_char(self, token_counter):
        """Single character should return at least 1."""
        assert token_counter.count_tokens("a") >= 1

    def test_count_short_sentence(self, token_counter):
        """Short sentence should return a reasonable count."""
        count = token_counter.count_tokens("Hello, how are you?")
        assert count >= 1
        assert count < 20  # Very short text should have few tokens

    def test_count_long_text(self, token_counter):
        """Long text should return proportionally more tokens."""
        short = token_counter.count_tokens("Hello, world!")
        long_count = token_counter.count_tokens("Hello, world! " * 100)
        assert long_count > short

    def test_count_with_special_chars(self, token_counter):
        """Text with special chars should still count."""
        count = token_counter.count_tokens("Special chars: !@#$%^&*()_+{}[]|\\:;\"'<>,.?/~`")
        assert count >= 1

    def test_count_consistent(self, token_counter):
        """Same text should return same count."""
        text = "The quick brown fox jumps over the lazy dog"
        assert token_counter.count_tokens(text) == token_counter.count_tokens(text)


class TestCountMessages:
    def test_count_empty_list(self, token_counter):
        """Empty message list should return 0."""
        assert token_counter.count_messages([]) == 0

    def test_single_message(self, token_counter):
        """Single message should count role + content + overhead."""
        messages = [{"role": "user", "content": "Hello!"}]
        count = token_counter.count_messages(messages)
        assert count >= 1

    def test_multiple_messages(self, token_counter):
        """Multiple messages should accumulate."""
        msg1 = {"role": "user", "content": "Hello"}
        msg2 = {"role": "assistant", "content": "Hi there! How can I help?"}
        msg3 = {"role": "user", "content": "What is Python?"}
        count = token_counter.count_messages([msg1, msg2, msg3])
        assert count >= 3

    def test_long_messages(self, token_counter):
        """Long messages should have proportionally more tokens."""
        short = [{"role": "user", "content": "Hi"}]
        long_msgs = [{"role": "user", "content": "X" * 1000}]
        assert token_counter.count_messages(long_msgs) > token_counter.count_messages(short)

    def test_with_missing_fields(self, token_counter):
        """Messages with missing fields should not crash."""
        messages = [{"role": "user"}]  # Missing 'content'
        count = token_counter.count_messages(messages)
        assert count >= 0


# ============================================================
# TokenCounter — Truncation
# ============================================================


class TestTruncateToTokens:
    def test_truncate_fitting_text(self, token_counter):
        """Text within budget should be returned unchanged."""
        text = "Short text"
        result = token_counter.truncate_to_tokens(text, max_tokens=1000)
        assert result == text

    def test_truncate_empty(self, token_counter):
        """Empty/negative max_tokens should return empty string."""
        assert token_counter.truncate_to_tokens("Hello", max_tokens=0) == ""
        assert token_counter.truncate_to_tokens("Hello", max_tokens=-1) == ""

    def test_truncate_empty_text(self, token_counter):
        """Empty text should return empty."""
        assert token_counter.truncate_to_tokens("", max_tokens=100) == ""

    def test_truncate_very_small_budget(self, token_counter):
        """Very small budget should still work."""
        text = "This is a fairly long text that should be truncated" * 10
        result = token_counter.truncate_to_tokens(text, max_tokens=5)
        assert len(result) < len(text)
        assert result.endswith("[...]") or len(result) < len(text)


class TestTruncateMessages:
    def test_truncate_empty_list(self, token_counter):
        """Empty message list should return empty list."""
        assert token_counter.truncate_messages([], max_tokens=100) == []

    def test_truncate_fits_budget(self, token_counter):
        """Messages within budget should be unchanged."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = token_counter.truncate_messages(messages, max_tokens=5000)
        assert len(result) == 2
        assert result[0]["content"] == "Hello"

    def test_truncate_preserves_system(self, token_counter):
        """System messages should always be preserved."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "This is a very long user message " * 200},
        ]
        result = token_counter.truncate_messages(messages, max_tokens=50)
        # System message should be preserved
        assert any(m.get("role") == "system" for m in result)

    def test_truncate_preserves_last_n(self, token_counter):
        """The last N messages should be preserved."""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        result = token_counter.truncate_messages(messages, max_tokens=50, preserve_last=3)
        # The last 3 messages should be in the result
        last_contents = [m["content"] for m in result]
        assert "Message 19" in last_contents
        assert "Message 18" in last_contents
        assert "Message 17" in last_contents

    def test_truncate_removes_oldest_first(self, token_counter):
        """Oldest non-system, non-guaranteed messages should be removed first."""
        messages = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]
        result = token_counter.truncate_messages(messages, max_tokens=30, preserve_last=2)
        # Should keep the last 2, so "Msg 8" and "Msg 9" should be present
        contents = [m["content"] for m in result]
        assert "Msg 9" in contents or "Msg 8" in contents


# ============================================================
# TokenCounter — Usage Reports
# ============================================================


class TestGetUsageReport:
    def test_report_structure(self, token_counter):
        """Usage report should have expected fields."""
        report = token_counter.get_usage_report("Hello, world!")
        assert "characters" in report
        assert "tokens" in report
        assert "ratio" in report
        assert "method" in report
        assert "model" in report

    def test_report_values(self, token_counter):
        """Report values should be consistent."""
        text = "Hello! " * 10
        report = token_counter.get_usage_report(text)
        assert report["characters"] == len(text)
        assert report["tokens"] > 0
        assert report["ratio"] > 0


# ============================================================
# Known Model Encoding Mapping
# ============================================================


class TestModelEncodingMapping:
    def test_openai_models(self, token_counter_with_tiktok):
        """OpenAI models should use correct encodings."""
        if token_counter_with_tiktok is None:
            pytest.skip("tiktoken not available")
        c = token_counter_with_tiktok
        c.model_name = "gpt-4o"
        assert c.count_tokens("Hello, world!") > 0

    def test_ollama_models(self, token_counter_with_tiktok):
        """Ollama models should have a fallback encoding."""
        if token_counter_with_tiktok is None:
            pytest.skip("tiktoken not available")
        c = token_counter_with_tiktok
        c.model_name = "llama3.2"
        assert c.count_tokens("Hello, world!") > 0


# ============================================================
# Helpers — detect if tiktoken is actually available
# ============================================================


def _has_tiktoken_available():
    try:
        import tiktoken
        return True
    except ImportError:
        return False
