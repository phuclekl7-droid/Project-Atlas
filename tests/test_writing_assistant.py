"""
Unit tests for Writing Assistant & Paraphraser Plugin.

Tests:
- Style definition constants
- Style detection from keywords (_detect_requested_style)
- Text extraction with command stripping (_extract_text_to_rewrite)
- Rewrite prompt builder (_build_rewrite_prompt)
- Basic rewrite transformations (_apply_basic_rewrite)
- Plugin execution flow
- Plugin metadata
- Error handling (empty input, non-rewrite input)
"""

import pytest

from src.plugin import BasePlugin, PluginResult
from src.plugins.writing_assistant import (
    WritingAssistantPlugin,
    STYLES,
    DEFAULT_STYLE,
    _detect_requested_style,
    _extract_text_to_rewrite,
    _build_rewrite_prompt,
    _apply_basic_rewrite,
)


# ============================================================
# Style Definitions Tests
# ============================================================


class TestStyleDefinitions:
    def test_all_styles_have_required_keys(self):
        for name, info in STYLES.items():
            assert "name" in info, f"Style {name} missing 'name'"
            assert "icon" in info, f"Style {name} missing 'icon'"
            assert "prompt_tag" in info, f"Style {name} missing 'prompt_tag'"
            assert "description" in info, f"Style {name} missing 'description'"

    def test_has_all_expected_styles(self):
        expected = {"professional", "friendly", "concise", "persuasive", "academic", "simple"}
        assert set(STYLES.keys()) == expected

    def test_default_style_is_valid(self):
        assert DEFAULT_STYLE in STYLES


# ============================================================
# Style Detection Tests
# ============================================================


class TestDetectRequestedStyle:
    def test_professional_vietnamese(self):
        assert _detect_requested_style("viết lại theo phong cách trang trọng") == "professional"

    def test_professional_english(self):
        assert _detect_requested_style("rewrite in professional style") == "professional"

    def test_friendly_vietnamese(self):
        assert _detect_requested_style("viết lại cho thân thiện hơn") == "friendly"

    def test_friendly_english(self):
        assert _detect_requested_style("make it more friendly") == "friendly"

    def test_concise_vietnamese(self):
        assert _detect_requested_style("viết ngắn gọn hơn") == "concise"

    def test_concise_english(self):
        assert _detect_requested_style("make it concise") == "concise"

    def test_academic(self):
        assert _detect_requested_style("rewrite in academic style") == "academic"

    def test_simple(self):
        assert _detect_requested_style("làm cho đơn giản hơn") == "simple"

    def test_persuasive(self):
        assert _detect_requested_style("viết theo phong cách thuyết phục") == "persuasive"

    def test_no_style_keyword(self):
        """No style keyword should return default."""
        assert _detect_requested_style("hello world") == DEFAULT_STYLE

    def test_empty_string(self):
        assert _detect_requested_style("") == DEFAULT_STYLE

    def test_multiple_keywords_picks_most(self):
        """Should pick the style with the most keyword matches."""
        text = "viết lại theo phong cách trang trọng, chuyên nghiệp, lịch sự"
        assert _detect_requested_style(text) == "professional"


# ============================================================
# Text Extraction Tests
# ============================================================


class TestExtractTextToRewrite:
    def test_removes_command_prefix(self):
        text, style = _extract_text_to_rewrite("viết lại Đây là văn bản cần viết lại")
        assert "Đây là văn bản cần viết lại" in text

    def test_removes_english_prefix(self):
        text, style = _extract_text_to_rewrite("rewrite This text needs rewriting")
        assert "This text needs rewriting" in text

    def test_detects_style(self):
        text, style = _extract_text_to_rewrite("viết lại theo phong cách thân thiện Xin chào bạn")
        assert style == "friendly"

    def test_short_text_falls_back(self):
        """If stripped text is too short, return original."""
        text, style = _extract_text_to_rewrite("viết lại ok")
        assert len(text) >= 10  # Falls back to original

    def test_no_command(self):
        """No command prefix should still detect style."""
        text, style = _extract_text_to_rewrite("hãy viết lại đoạn văn này trang trọng hơn")
        assert len(text) > 0
        assert style == "professional"


# ============================================================
# Rewrite Prompt Builder Tests
# ============================================================


class TestBuildRewritePrompt:
    def test_contains_text_and_style(self):
        prompt = _build_rewrite_prompt("Hello world", "professional")
        assert "Hello world" in prompt
        assert "Professional" in prompt

    def test_contains_prompt_tag(self):
        prompt = _build_rewrite_prompt("Test", "friendly")
        assert "[CASUAL]" in prompt

    def test_contains_instruction(self):
        prompt = _build_rewrite_prompt("Test", "concise")
        assert "viết lại" in prompt.lower()

    def test_unknown_style_falls_back_to_default(self):
        prompt = _build_rewrite_prompt("Test", "nonexistent_style")
        assert "Professional" in prompt


# ============================================================
# Basic Rewrite Tests
# ============================================================


class TestApplyBasicRewrite:
    def test_concise_removes_filler_words(self):
        result = _apply_basic_rewrite("thực sự rất là tốt", "concise")
        assert "thực sự" not in result
        assert "rất là" not in result

    def test_concise_shortens(self):
        result = _apply_basic_rewrite("This is a long sentence. This is another one. And a third.", "concise")
        sentences = result.split(".")
        # Should have at most 2 sentences
        non_empty = [s for s in sentences if s.strip()]
        assert len(non_empty) <= 2

    def test_simple_replaces_complex_words(self):
        result = _apply_basic_rewrite("tuy nhiên, do đó chúng tôi triển khai", "simple")
        assert "nhưng" in result
        assert "vì vậy" in result
        assert "làm" in result

    def test_friendly_adds_emoji(self):
        result = _apply_basic_rewrite("Hello", "friendly")
        assert "😊" in result

    def test_friendly_ensures_punctuation(self):
        result = _apply_basic_rewrite("Hi", "friendly")
        assert result.endswith("!") or result.endswith(".")

    def test_no_change_for_unknown_style(self):
        result = _apply_basic_rewrite("Hello world", "professional")
        assert result is not None


# ============================================================
# Plugin Metadata Tests
# ============================================================


class TestWritingAssistantMetadata:
    def test_plugin_name(self):
        plugin = WritingAssistantPlugin()
        assert plugin.name == "writing_assistant"

    def test_plugin_description(self):
        plugin = WritingAssistantPlugin()
        assert plugin.description is not None
        assert len(plugin.description) > 0
        assert "Viết lại" in plugin.description or "rewrite" in plugin.description.lower()

    def test_is_baseplugin_subclass(self):
        assert issubclass(WritingAssistantPlugin, BasePlugin)


# ============================================================
# Plugin Execution Tests
# ============================================================


class TestWritingAssistantExecute:
    def test_empty_input(self):
        plugin = WritingAssistantPlugin()
        result = plugin.execute("")
        assert result.success is False
        assert result.output == ""

    def test_non_rewrite_input(self):
        """Input without rewrite keywords should return empty."""
        plugin = WritingAssistantPlugin()
        result = plugin.execute("Hello, how are you?")
        assert result.success is False
        assert result.output == ""

    def test_vietnamese_rewrite_request(self):
        """Vietnamese rewrite request should succeed."""
        plugin = WritingAssistantPlugin()
        result = plugin.execute("viết lại Đây là văn bản cần viết lại theo phong cách trang trọng")
        assert result.success is True
        assert "Viết lại" in result.output

    def test_english_rewrite_request(self):
        """English rewrite request should succeed."""
        plugin = WritingAssistantPlugin()
        result = plugin.execute("rewrite This text needs rewriting in professional style")
        assert result.success is True

    def test_concise_style(self):
        """Concise style should apply transformation."""
        plugin = WritingAssistantPlugin()
        result = plugin.execute("viết lại ngắn gọn Đây là một đoạn văn rất dài. Nó có nhiều câu. Câu cuối cùng.")
        assert result.success is True

    def test_result_contains_data(self):
        """Result should have data with style info."""
        plugin = WritingAssistantPlugin()
        result = plugin.execute("viết lại This is a test paragraph.")
        assert result.data is not None
        assert "style" in result.data
        assert "original_length" in result.data
        assert "rewritten_length" in result.data
