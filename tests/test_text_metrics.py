"""
Unit tests for Text Metrics (Word Counter & Reading Time).

Tests:
- count_words with English text
- count_words with Vietnamese text (contains CJK-like chars)
- count_words with mixed content
- count_words with empty/None
- count_sentences
- count_cjk_chars
- compute_reading_time
- compute_text_metrics full pipeline
- render_metrics_html for long vs short text
- Edge cases: single word, code blocks, numbers
"""

import pytest

from utils.text_metrics import (
    TextMetrics,
    count_words,
    count_sentences,
    count_cjk_chars,
    has_cjk_text,
    compute_reading_time,
    compute_text_metrics,
    render_metrics_html,
)


class TestCountWords:
    def test_english_simple(self):
        assert count_words("Hello world") == 2

    def test_english_multiple(self):
        assert count_words("This is a test of the word counter") == 7

    def test_empty(self):
        assert count_words("") == 0

    def test_whitespace(self):
        assert count_words("   ") == 0

    def test_vietnamese(self):
        """Vietnamese words are separated by spaces, like English."""
        assert count_words("Xin chào thế giới") == 4

    def test_mixed_cjk(self):
        """Chinese characters each count as one word."""
        text = "Hello 世界 你好 world"
        assert count_words(text) == 6  # 3 English + 3 Chinese

    def test_single_word(self):
        assert count_words("Hello") == 1

    def test_with_punctuation(self):
        assert count_words("Hello, world! How are you?") == 5

    def test_numbers(self):
        assert count_words("There are 42 items") == 4

    def test_code_snippet(self):
        code = "def hello():\n    print('hi')\n    return 42"
        assert count_words(code) >= 5


class TestCountSentences:
    def test_simple(self):
        assert count_sentences("Hello world. How are you?") == 2

    def test_single(self):
        assert count_sentences("Just one sentence.") == 1

    def test_empty(self):
        assert count_sentences("") == 0

    def test_exclamation(self):
        assert count_sentences("Watch out! Look!") == 2

    def test_newline_separated(self):
        assert count_sentences("Line one\nLine two\nLine three") >= 2


class TestCountCjkChars:
    def test_no_cjk(self):
        assert count_cjk_chars("Hello world") == 0

    def test_with_cjk(self):
        assert count_cjk_chars("Hello 世界") == 2

    def test_all_cjk(self):
        assert count_cjk_chars("你好世界") == 4

    def test_empty(self):
        assert count_cjk_chars("") == 0

    def test_mixed(self):
        assert count_cjk_chars("123 !@#") == 0


class TestHasCjkText:
    def test_has_cjk(self):
        assert has_cjk_text("Hello 世界") is True

    def test_no_cjk(self):
        assert has_cjk_text("Hello world") is False

    def test_empty(self):
        assert has_cjk_text("") is False


class TestComputeReadingTime:
    def test_english_only(self):
        """200 words at 200 wpm = 1 minute = 60 seconds."""
        time_sec = compute_reading_time(200, cjk_count=0)
        assert 55 <= time_sec <= 65

    def test_zero_words(self):
        assert compute_reading_time(0) == 0.0

    def test_cjk_reading_time(self):
        """300 CJK chars at 300 cpm = 1 minute = 60 seconds."""
        time_sec = compute_reading_time(300, cjk_count=300)
        assert 55 <= time_sec <= 65

    def test_mixed_reading_time(self):
        """100 alpha + 150 cjk = mixed time."""
        time_sec = compute_reading_time(250, cjk_count=150)
        assert time_sec > 0


class TestComputeTextMetrics:
    def test_empty_text(self):
        metrics = compute_text_metrics("")
        assert metrics.word_count == 0
        assert metrics.char_count == 0

    def test_english(self):
        text = "The quick brown fox jumps over the lazy dog."
        metrics = compute_text_metrics(text)
        assert metrics.word_count == 9
        assert metrics.char_count == 44
        assert metrics.sentence_count == 1
        assert metrics.cjk_char_count == 0
        assert metrics.has_cjk is False
        assert metrics.reading_time_seconds > 0

    def test_vietnamese(self):
        text = "Xin chào! Hôm nay là một ngày đẹp trời."
        metrics = compute_text_metrics(text)
        assert metrics.word_count >= 5
        assert metrics.char_count > 10
        assert metrics.sentence_count >= 1

    def test_long_text(self):
        text = "Hello world. " * 50
        metrics = compute_text_metrics(text)
        assert metrics.word_count == 100  # "Hello" + "world." × 50
        assert metrics.char_count > 100

    def test_char_count_no_spaces(self):
        text = "Hello world"
        metrics = compute_text_metrics(text)
        assert metrics.char_count == 11
        assert metrics.char_count_no_spaces == 10  # "Helloworld"


class TestRenderMetricsHtml:
    def test_long_text_returns_html(self):
        text = "This is a sufficiently long text that should produce metrics. " * 5
        metrics = compute_text_metrics(text)
        html = render_metrics_html(metrics)
        assert html != ""
        assert "📝" in html
        assert "⏱️" in html
        assert "từ" in html or "phút" in html

    def test_short_text_returns_empty(self):
        text = "Hi!"
        metrics = compute_text_metrics(text)
        assert render_metrics_html(metrics) == ""

    def test_empty_text(self):
        assert render_metrics_html(TextMetrics()) == ""

    def test_format_under_one_minute(self):
        text = "Hello, this is a test of the reading time feature. " * 3
        metrics = compute_text_metrics(text)
        html = render_metrics_html(metrics)
        assert html != ""
        assert "phút" in html

    def test_format_multi_minute(self):
        text = "Hello world. " * 100
        metrics = compute_text_metrics(text)
        html = render_metrics_html(metrics)
        assert "phút" in html
