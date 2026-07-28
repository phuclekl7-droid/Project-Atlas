"""
Tests for Language Learning Tutor Plugin (Feature #96).

Tests the plugin's parsing, rule-based grammar checking,
and configuration handling. AI-powered features are tested
with a mock ModelRouter.
"""

import pytest
from src.plugins.language_tutor import (
    LanguageTutorPlugin,
    _detect_language,
    _parse_tutor_config,
    _build_system_prompt,
    TutorConfig,
)


# ============================================================
# Fixtures
# ============================================================


class MockModelRouter:
    """Simple mock for testing plugin AI features."""

    def generate(self, prompt: str, **kwargs):
        class MockResponse:
            text = f"Mock response for: {prompt[:50]}..."
        return MockResponse()


@pytest.fixture
def plugin():
    return LanguageTutorPlugin()


@pytest.fixture
def mock_router():
    return MockModelRouter()


# ============================================================
# Tests: _detect_language()
# ============================================================


class TestDetectLanguage:
    def test_detect_vietnamese(self):
        text = "Xin chào, tôi là sinh viên"
        result = _detect_language(text)
        assert result == "vi"

    def test_detect_japanese(self):
        text = "こんにちは、元気ですか"
        result = _detect_language(text)
        assert result == "ja"

    def test_detect_english_fallback(self):
        text = "Hello, how are you today?"
        result = _detect_language(text)
        assert result == "en"

    def test_detect_empty(self):
        assert _detect_language("") == "en"

    def test_detect_mixed(self):
        text = "Hello, xin chào"
        result = _detect_language(text)
        assert result == "vi"


# ============================================================
# Tests: _parse_tutor_config()
# ============================================================


class TestParseTutorConfig:
    def test_parse_language(self):
        config = _parse_tutor_config("lang=en")
        assert config.language == "en"

    def test_parse_language_vietnamese(self):
        config = _parse_tutor_config("lang=vi")
        assert config.language == "vi"

    def test_parse_level(self):
        config = _parse_tutor_config("lang=ja level=B1")
        assert config.language == "ja"
        assert config.level == "b1"

    def test_parse_mode(self):
        config = _parse_tutor_config("lang=en mode=grammar")
        assert config.language == "en"
        assert config.mode == "grammar"

    def test_parse_native(self):
        config = _parse_tutor_config("lang=en native=vi")
        assert config.language == "en"
        assert config.native_language == "vi"

    def test_parse_full_config(self):
        config = _parse_tutor_config("lang=fr level=A2 mode=vocab native=en")
        assert config.language == "fr"
        assert config.level == "a2"
        assert config.mode == "vocab"
        assert config.native_language == "en"

    def test_parse_default_values(self):
        config = _parse_tutor_config("")
        assert config.language == "en"
        assert config.level == "beginner"
        assert config.mode == "conversation"
        assert config.native_language == "vi"


# ============================================================
# Tests: _build_system_prompt()
# ============================================================


class TestBuildSystemPrompt:
    def test_grammar_mode(self):
        config = TutorConfig(mode="grammar", language="en")
        prompt = _build_system_prompt(config)
        assert "grammar tutor" in prompt.lower()

    def test_vocab_mode(self):
        config = TutorConfig(mode="vocab", language="en")
        prompt = _build_system_prompt(config)
        assert "vocabulary" in prompt.lower()

    def test_conversation_mode(self):
        config = TutorConfig(mode="conversation", language="en")
        prompt = _build_system_prompt(config)
        assert "conversation" in prompt.lower()

    def test_writing_mode(self):
        config = TutorConfig(mode="writing", language="en")
        prompt = _build_system_prompt(config)
        assert "writing" in prompt.lower()

    def test_unknown_mode_falls_to_conversation(self):
        config = TutorConfig(mode="unknown", language="en")
        prompt = _build_system_prompt(config)
        assert "conversation" in prompt.lower()

    def test_vietnamese_language(self):
        config = TutorConfig(mode="grammar", language="vi", native_language="en")
        prompt = _build_system_prompt(config)
        assert "Tiếng Việt" in prompt


# ============================================================
# Tests: LanguageTutorPlugin.execute()
# ============================================================


class TestPluginExecute:
    def test_empty_input_returns_help(self, plugin):
        result = plugin.execute("")
        assert not result.success
        assert "Tutor" in result.error

    def test_whitespace_input_returns_help(self, plugin):
        result = plugin.execute("   ")
        assert not result.success

    def test_tutor_config_command(self, plugin):
        result = plugin.execute("tutor lang=en mode=grammar")
        assert result.success
        assert "Language:" in result.output
        assert "English" in result.output
        assert "Grammar" in result.output

    def test_tutor_config_vietnamese(self, plugin):
        result = plugin.execute("tutor lang=vi level=A1 mode=conversation")
        assert result.success
        assert "Tiếng Việt" in result.output or "Language:" in result.output

    def test_grammar_check_command(self, plugin):
        """Test that grammar check returns results with issues."""
        sentence = "He don't like coffee"
        result = plugin.execute(f"grammar: {sentence}")
        assert result.success
        assert "doesn't" in result.output.lower()

    def test_grammar_check_correct_sentence(self, plugin):
        """Test that a correct sentence passes basic checks."""
        sentence = "She goes to school every day."
        result = plugin.execute(f"grammar: {sentence}")
        assert result.success
        assert "Looks Good" in result.output

    def test_grammar_missing_punctuation(self, plugin):
        sentence = "hello world"
        result = plugin.execute(f"grammar: {sentence}")
        assert result.success
        assert any(word in result.output.lower() for word in ["punctuation", "capital"])

    def test_grammar_article_a_an(self, plugin):
        """Test 'a' before vowel detection."""
        sentence = "He is a apple farmer"
        result = plugin.execute(f"grammar: {sentence}")
        assert result.success
        assert "a" in result.output.lower() and "an" in result.output.lower()

    def test_vocab_command(self, plugin):
        result = plugin.execute("vocab: serendipity")
        assert result.success
        assert "serendipity" in result.output

    def test_practice_command(self, plugin):
        result = plugin.execute("practice: my favorite hobby")
        assert result.success
        assert "Practice" in result.output or "Talk" in result.output

    def test_exercises_command(self, plugin):
        result = plugin.execute("exercises")
        assert result.success
        assert "Exercises" in result.output or "exercise" in result.output.lower()

    def test_unknown_command_returns_help(self, plugin):
        result = plugin.execute("some random text")
        assert not result.success
        assert "Tutor" in result.error or "Help" in result.error

    def test_grammar_with_mock_router(self, plugin, mock_router):
        """Test grammar check with mock model router."""
        result = plugin.execute("grammar: This is a test", model_router=mock_router)
        assert result.success
        # Should have model response or fallback
        assert result.output

    def test_practice_with_mock_router(self, plugin, mock_router):
        """Test practice with mock model router."""
        result = plugin.execute(
            "practice: Tell me about yourself",
            model_router=mock_router,
        )
        assert result.success
        assert result.output

    def test_vocab_with_mock_router(self, plugin, mock_router):
        result = plugin.execute("vocab: resilience", model_router=mock_router)
        assert result.success
        assert "resilience" in result.output

    def test_multiple_grammar_checks_preserve_state(self, plugin):
        """Ensure grammar checks don't corrupt plugin state."""
        result1 = plugin.execute("grammar: He go to school")
        assert result1.success
        result2 = plugin.execute("grammar: She don't like pizza")
        assert result2.success
        result3 = plugin.execute("vocab: hello")
        assert result3.success


# ============================================================
# Tests: Rule-Based Grammar Check
# ============================================================


class TestRuleBasedGrammarCheck:
    def test_subject_verb_agreement(self, plugin):
        result = plugin._rule_based_grammar_check("He don't know")
        assert "doesn't" in result

    def test_double_comparative(self, plugin):
        result = plugin._rule_based_grammar_check("She is more smarter")
        assert "comparative" in result.lower()

    def test_no_issues(self, plugin):
        result = plugin._rule_based_grammar_check("She goes to school every day.")
        assert "Looks Good" in result

    def test_empty_sentence(self, plugin):
        result = plugin._rule_based_grammar_check("")
        assert "Looks Good" in result


# ============================================================
# Tests: Help text
# ============================================================


class TestHelpText:
    def test_help_contains_supported_languages(self, plugin):
        help_text = plugin._get_help_text()
        assert "en" in help_text
        assert "vi" in help_text
        assert "ja" in help_text

    def test_help_contains_commands(self, plugin):
        help_text = plugin._get_help_text()
        assert "grammar" in help_text.lower()
        assert "vocab" in help_text.lower()
        assert "practice" in help_text.lower()
        assert "exercises" in help_text.lower()
