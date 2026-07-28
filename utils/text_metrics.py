"""
Text Metrics (Feature 168: Word Counter & Reading Time)

Computes word count, character count, and estimated reading time for
AI response messages.

Usage:
    metrics = compute_text_metrics("Your text here...")
    html = render_metrics_html(metrics)
    # -> "📝 450 từ | ⏱️ ~2 phút đọc"
"""

import re
from dataclasses import dataclass

# Average reading speed: 200 words per minute (Vietnamese/English)
_WORDS_PER_MINUTE = 200

# Average reading speed for CJK characters (characters per minute)
_CJK_CHARS_PER_MINUTE = 300


@dataclass
class TextMetrics:
    """Computed text metrics for a message."""
    word_count: int = 0
    char_count: int = 0
    char_count_no_spaces: int = 0
    sentence_count: int = 0
    reading_time_seconds: float = 0.0
    reading_time_minutes: float = 0.0
    cjk_char_count: int = 0  # Chinese/Japanese/Korean characters
    has_cjk: bool = False


def count_words(text: str) -> int:
    """
    Count words in text, handling both alphabetic and CJK languages.

    For alphabetic languages, splits on whitespace.
    For CJK, each character counts as one word.
    Mixed content is handled by combining both approaches.
    """
    if not text or not text.strip():
        return 0

    text = text.strip()

    # Count CJK characters (each counts as one word)
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))

    # Remove CJK chars and count remaining words by whitespace
    non_cjk = re.sub(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', '', text)
    alpha_words = len([w for w in non_cjk.split() if w.strip()])

    return cjk_chars + alpha_words


def count_sentences(text: str) -> int:
    """Count the number of sentences in the text."""
    if not text or not text.strip():
        return 0
    # Split by sentence-ending punctuation
    sentences = re.split(r'[.!?\n]+', text.strip())
    return len([s for s in sentences if s.strip()])


def count_cjk_chars(text: str) -> int:
    """Count CJK (Chinese/Japanese/Korean) characters in text."""
    if not text:
        return 0
    return len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))


def has_cjk_text(text: str) -> bool:
    """Check if text contains CJK characters."""
    return count_cjk_chars(text) > 0


def compute_reading_time(word_count: int, cjk_count: int = 0) -> float:
    """
    Compute estimated reading time in seconds.

    Uses different speeds for alphabetic vs CJK text.
    Blended rate when both are present.

    Args:
        word_count: Total word count (including CJK as individual words)
        cjk_count: Number of CJK characters

    Returns:
        Reading time in seconds
    """
    non_cjk_words = word_count - cjk_count
    if word_count <= 0:
        return 0.0

    # Time for alphabetic words
    alpha_time = (non_cjk_words / _WORDS_PER_MINUTE) * 60 if non_cjk_words > 0 else 0

    # Time for CJK characters
    cjk_time = (cjk_count / _CJK_CHARS_PER_MINUTE) * 60 if cjk_count > 0 else 0

    return alpha_time + cjk_time


def compute_text_metrics(text: str) -> TextMetrics:
    """
    Compute all text metrics for the given text.

    Args:
        text: The text to analyze

    Returns:
        TextMetrics dataclass with all computed values
    """
    if not text:
        return TextMetrics()

    word_count = count_words(text)
    char_count = len(text)
    char_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\r", ""))
    sentence_count = count_sentences(text)
    cjk_count = count_cjk_chars(text)
    reading_time = compute_reading_time(word_count, cjk_count)

    return TextMetrics(
        word_count=word_count,
        char_count=char_count,
        char_count_no_spaces=char_no_spaces,
        sentence_count=sentence_count,
        reading_time_seconds=reading_time,
        reading_time_minutes=reading_time / 60,
        cjk_char_count=cjk_count,
        has_cjk=cjk_count > 0,
    )


def render_metrics_html(metrics: TextMetrics) -> str:
    """
    Render text metrics as an HTML string for the UI.

    Args:
        metrics: TextMetrics object from compute_text_metrics()

    Returns:
        HTML string like "📝 450 từ | ⏱️ ~2 phút đọc"
        Returns empty string if text is too short (< 20 chars).
    """
    if metrics.char_count < 20 or metrics.word_count <= 0:
        return ""

    # Format reading time
    if metrics.reading_time_minutes < 1:
        reading_str = f"<{1} phút"
    elif metrics.reading_time_minutes < 2:
        reading_str = "~1 phút"
    else:
        reading_str = f"~{int(round(metrics.reading_time_minutes))} phút"

    return (
        f'<div style="font-size:0.65rem;color:#888;text-align:right;'
        f'padding:0.1rem 0.3rem;margin-top:-0.2rem;">'
        f'📝 {metrics.word_count:,} từ · {metrics.char_count:,} ký tự · '
        f'⏱️ {reading_str} đọc'
        f'</div>'
    )
