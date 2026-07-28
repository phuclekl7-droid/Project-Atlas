"""
Language Learning Tutor Plugin (Feature #96)

Uses the ModelRouter to act as an interactive language tutor.
Supports grammar correction, vocabulary building, pronunciation tips,
and multi-language conversation practice.

Usage:
    /tutor lang=en          — Start English tutoring session
    /tutor lang=vi          — Start Vietnamese tutoring session
    /tutor grammar: ...     — Check grammar
    /tutor vocab: ...       — Vocabulary explanation
    /tutor practice: ...    — Conversation practice prompt
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from src.plugin import BasePlugin, PluginResult

logger = logging.getLogger("plugins.language_tutor")


@dataclass
class TutorConfig:
    """Configuration for a tutoring session."""

    language: str = "en"
    level: str = "beginner"
    mode: str = "conversation"  # grammar, vocab, conversation, writing
    target_language: str = ""
    native_language: str = "vi"
    max_exercises: int = 5


# ── Language metadata ──

_LANGUAGE_NAMES = {
    "en": "English",
    "vi": "Tiếng Việt",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "zh": "中文 (Chinese)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
    "es": "Español (Spanish)",
    "it": "Italiano (Italian)",
    "pt": "Português (Portuguese)",
    "ru": "Русский (Russian)",
    "th": "ไทย (Thai)",
}

_SUPPORTED_LANGS = sorted(_LANGUAGE_NAMES.keys())


def _detect_language(text: str) -> str:
    """Roughly detect the language of the text (used for mode detection)."""
    vietnamese_chars = set("ăâđêôơưừệẫễảấ") & set(text.lower())
    if vietnamese_chars:
        return "vi"
    jp_chars = set("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん") & set(text)
    if jp_chars:
        return "ja"
    return "en"


def _build_system_prompt(config: TutorConfig) -> str:
    """Build the system prompt for the AI tutor."""
    lang = config.language
    lang_name = _LANGUAGE_NAMES.get(lang, lang.upper())
    native = _LANGUAGE_NAMES.get(config.native_language, config.native_language)

    prompts = {
        "grammar": (
            f"You are a {lang_name} grammar tutor. Your student's native language is {native}. "
            f"Analyze the following text for grammar errors. For each error:\n"
            f"1. Point out the mistake\n"
            f"2. Explain WHY it's wrong in simple terms\n"
            f"3. Show the corrected version\n"
            f"4. Provide a similar example\n"
            f"Be encouraging and patient. Use {native} for explanations when needed."
        ),
        "vocab": (
            f"You are a {lang_name} vocabulary teacher. Your student's native language is {native}. "
            f"Explain the meaning, usage, and examples of the requested word/phrase. Include:\n"
            f"1. Definition in {lang_name}\n"
            f"2. Translation in {native}\n"
            f"3. 2-3 example sentences\n"
            f"4. Common collocations\n"
            f"5. Memory tips (mnemonics, cognates)"
        ),
        "conversation": (
            f"You are a {lang_name} conversation partner at level: {config.level}. "
            f"Your student's native language is {native}. Follow these rules:\n"
            f"1. Start conversations naturally\n"
            f"2. If the student makes errors, gently correct them\n"
            f"3. Adjust complexity to their level\n"
            f"4. Encourage them to express themselves\n"
            f"5. Suggest better expressions when appropriate\n"
            f"Use CEFR levels: A1/A2 (beginner), B1/B2 (intermediate), C1/C2 (advanced)."
        ),
        "writing": (
            f"You are a {lang_name} writing coach. Your student's native language is {native}. "
            f"Review the student's writing and provide feedback on:\n"
            f"1. Grammar and syntax\n"
            f"2. Vocabulary choice\n"
            f"3. Style and tone\n"
            f"4. Organization and flow\n"
            f"5. Suggestions for improvement\n"
            f"Always show the corrected version and explain changes."
        ),
    }
    return prompts.get(config.mode, prompts["conversation"])


def _parse_tutor_config(text: str) -> TutorConfig:
    """Parse tutor configuration from text input.

    Supported formats:
        /tutor lang=en            — set language
        /tutor lang=en level=B1   — set language + level
        /tutor mode=grammar       — set mode
    """
    config = TutorConfig()

    # Parse lang=XX
    lang_match = re.search(r'lang=(\w+)', text)
    if lang_match:
        lang = lang_match.group(1).lower()
        if lang in _LANGUAGE_NAMES:
            config.language = lang

    # Parse level=XX
    level_match = re.search(r'level=(\w+)', text)
    if level_match:
        level = level_match.group(1).lower()
        if level in ("a1", "a2", "b1", "b2", "c1", "c2", "beginner", "intermediate", "advanced"):
            config.level = level

    # Parse mode=XX
    mode_match = re.search(r'mode=(\w+)', text)
    if mode_match:
        mode = mode_match.group(1).lower()
        if mode in ("grammar", "vocab", "conversation", "writing"):
            config.mode = mode

    # Parse native=XX
    native_match = re.search(r'native=(\w+)', text)
    if native_match:
        nat = native_match.group(1).lower()
        if nat in _LANGUAGE_NAMES:
            config.native_language = nat

    return config


class LanguageTutorPlugin(BasePlugin):
    """Interactive language learning tutor using AI.

    Supports multiple languages, modes (grammar/vocab/conversation/writing),
    and CEFR levels. Uses the ModelRouter for intelligent responses.

    Usage:
        /tutor lang=en              — Start English session
        /tutor lang=ja level=A1     — Japanese for beginners
        /tutor grammar: ...         — Check grammar
        /tutor vocab: ...           — Explain vocabulary
        /tutor practice: ...        — Practice conversation
    """

    name = "language_tutor"
    description = "Interactive AI language tutor: grammar, vocab, conversation practice"

    def __init__(self):
        super().__init__()
        self._sessions: dict[str, TutorConfig] = {}

    def execute(self, input_str: str, **kwargs) -> PluginResult:
        """Execute the language tutor command.

        Args:
            input_str: Full command text
            **kwargs: May contain 'model_router' for AI-powered responses

        Returns:
            PluginResult with tutor output
        """
        if not input_str or not input_str.strip():
            return PluginResult(
                success=False,
                error=self._get_help_text(),
            )

        text = input_str.strip()

        # ── Configuration commands ──
        if text.lower().startswith("tutor"):
            body = text[5:].strip().lower()
            if body.startswith("lang=") or body.startswith("mode=") or body.startswith("level=") or body.startswith("native="):
                config = _parse_tutor_config(body)
                session_key = f"tutor_{config.language}"
                self._sessions[session_key] = config
                lang_name = _LANGUAGE_NAMES.get(config.language, config.language.upper())
                return PluginResult(
                    success=True,
                    output=(
                        f"## 🎓 Language Tutor\n\n"
                        f"**Language:** {lang_name}\n"
                        f"**Level:** {config.level.upper()}\n"
                        f"**Mode:** {config.mode.capitalize()}\n"
                        f"**Native:** {_LANGUAGE_NAMES.get(config.native_language, config.native_language)}\n\n"
                        f"Ready to learn! Try:\n"
                        f"- `grammar: <your sentence>`\n"
                        f"- `vocab: <word>`\n"
                        f"- `practice: <topic>`\n"
                        f"- `exercises` — get {config.max_exercises} exercises"
                    ),
                    data={
                        "action": "config",
                        "language": config.language,
                        "mode": config.mode,
                        "level": config.level,
                    },
                )

        # ── Grammar check ──
        grammar_match = re.match(r'(?:grammar|check)\s*:\s*(.+)$', text, re.IGNORECASE)
        if grammar_match:
            sentence = grammar_match.group(1).strip()
            model_router = kwargs.get("model_router")
            if model_router:
                config = self._get_session_config(text)
                system = _build_system_prompt(config)
                prompt = (
                    f"{system}\n\n"
                    f"Student's text to check: \"{sentence}\"\n\n"
                    f"Check this sentence for grammar errors. "
                    f"Respond in a structured format with: error, explanation, correction, example."
                )
                try:
                    response = model_router.generate(prompt)
                    output = response.text if hasattr(response, "text") else str(response)
                    return PluginResult(
                        success=True,
                        output=f"## 📝 Grammar Check\n\n{output}",
                        data={"action": "grammar", "sentence": sentence},
                    )
                except Exception as e:
                    logger.warning(f"AI grammar check failed, falling back to rule-based: {e}")

            return PluginResult(
                success=True,
                output=self._rule_based_grammar_check(sentence),
                data={"action": "grammar_fallback", "sentence": sentence},
            )

        # ── Vocabulary ──
        vocab_match = re.match(r'(?:vocab|word|define)\s*:\s*(.+)$', text, re.IGNORECASE)
        if vocab_match:
            word = vocab_match.group(1).strip()
            model_router = kwargs.get("model_router")
            if model_router:
                config = self._get_session_config(text)
                system = _build_system_prompt(config)
                prompt = (
                    f"{system}\n\n"
                    f"Word/phrase to explain: \"{word}\"\n\n"
                    f"Provide a comprehensive explanation."
                )
                try:
                    response = model_router.generate(prompt)
                    output = response.text if hasattr(response, "text") else str(response)
                    return PluginResult(
                        success=True,
                        output=f"## 📖 Vocabulary: {word}\n\n{output}",
                        data={"action": "vocab", "word": word},
                    )
                except Exception as e:
                    logger.warning(f"AI vocab lookup failed, falling back to text: {e}")

            return PluginResult(
                success=True,
                output=(
                    f"## 📖 Vocabulary: {word}\n\n"
                    f"*To get a full AI-powered explanation with examples, "
                    f"make sure a ModelRouter is available.*\n\n"
                    f"**Word:** {word}\n"
                    f"**Hint:** Try looking up this word in a dictionary "
                    f"or set up an AI provider (OpenAI/Gemini/Ollama) for detailed explanations."
                ),
                data={"action": "vocab", "word": word},
            )

        # ── Conversation practice ──
        practice_match = re.match(r'(?:practice|talk|chat)\s*:\s*(.+)$', text, re.IGNORECASE)
        if practice_match or text.lower().startswith(("conversation", "dialogue")):
            topic = practice_match.group(1).strip() if practice_match else text
            model_router = kwargs.get("model_router")
            if model_router:
                config = self._get_session_config(text)
                system = _build_system_prompt(config)
                prompt = (
                    f"{system}\n\n"
                    f"Practice topic: \"{topic}\"\n\n"
                    f"Start a natural conversation about this topic. "
                    f"Ask questions and encourage the student to respond."
                )
                try:
                    response = model_router.generate(prompt)
                    output = response.text if hasattr(response, "text") else str(response)
                    return PluginResult(
                        success=True,
                        output=f"## 💬 Conversation Practice\n\n{output}",
                        data={"action": "practice", "topic": topic},
                    )
                except Exception as e:
                    logger.warning(f"AI practice failed, falling back to text: {e}")

            return PluginResult(
                success=True,
                output=(
                    f"## 💬 Let's Talk!\n\n"
                    f"**Topic:** {topic}\n\n"
                    f"To practice, try:\n"
                    f"1. Write a few sentences about this topic\n"
                    f"2. Use `grammar: <text>` to check your writing\n"
                    f"3. Use `vocab: <word>` to learn new words\n\n"
                    f"Or connect an AI provider for interactive conversation practice!"
                ),
                data={"action": "practice", "topic": topic},
            )

        # ── Exercises command ──
        if text.lower().startswith(("exercise", "quiz")):
            config = self._get_session_config(text)
            model_router = kwargs.get("model_router")
            if model_router:
                system = _build_system_prompt(config)
                prompt = (
                    f"{system}\n\n"
                    f"Generate {config.max_exercises} exercises for a {config.level} student. "
                    f"Include a mix of: fill-in-the-blank, multiple choice, "
                    f"and sentence transformation. Provide the answer key after the exercises."
                )
                try:
                    response = model_router.generate(prompt)
                    output = response.text if hasattr(response, "text") else str(response)
                    return PluginResult(
                        success=True,
                        output=f"## 📝 Exercises\n\n{output}",
                        data={"action": "exercises"},
                    )
                except Exception as e:
                    logger.warning(f"AI exercises generation failed, falling back to static: {e}")

            return PluginResult(
                success=True,
                output=(
                    f"## 📝 {config.max_exercises} Quick Exercises\n\n"
                    f"1. **Fill in:** She ___ (go) to school every day.\n"
                    f"2. **Choose:** I ___ a student. (am/is/are)\n"
                    f"3. **Correct:** 'He don't like coffee.' → ?\n"
                    f"4. **Translate:** 'Tôi thích học tiếng Anh'\n"
                    f"5. **Complete:** If I had more time, I ___\n\n"
                    f"Check your answers with `grammar: <your answer>`"
                ),
                data={"action": "exercises"},
            )

        # ── Fallback: show help ──
        return PluginResult(
            success=False,
            error=self._get_help_text(),
        )

    def _get_session_config(self, text: str) -> TutorConfig:
        """Get or create a tutor config for the current session."""
        lang = _detect_language(text)
        session_key = f"tutor_{lang}"
        return self._sessions.get(session_key, TutorConfig(language=lang))

    @staticmethod
    def _rule_based_grammar_check(sentence: str) -> str:
        """Simple rule-based grammar check (fallback when AI unavailable)."""
        issues = []

        # Check subject-verb agreement (basic)
        if re.search(r'\b(he|she|it)\s+don\'t\b', sentence, re.IGNORECASE):
            issues.append("❌ 'He/She/It don't' → should be 'doesn't'")
        if re.search(r'\b(I|you|we|they)\s+doesn\'t\b', sentence, re.IGNORECASE):
            issues.append("❌ 'I/You/We/They doesn't' → should be 'don't'")

        # Check article usage
        if re.search(r'\ba\s+[aeiou]', sentence, re.IGNORECASE):
            issues.append("⚠️ 'a' before a vowel sound → should be 'an'")
        if re.search(r'\ban\s+[^aeiou\s]', sentence[:15], re.IGNORECASE):
            issues.append("⚠️ 'an' before a consonant sound → should be 'a'")

        # Check common grammar mistakes
        if re.search(r'\bmore\s+\w+er\b', sentence, re.IGNORECASE):
            issues.append("❌ Double comparative: 'more X-er' → use either 'more X' or 'X-er'")
        if re.search(r'\bmost\s+\w+est\b', sentence, re.IGNORECASE):
            issues.append("❌ Double superlative: 'most X-est' → use either 'most X' or 'X-est'")

        # Check for missing punctuation
        if sentence and not sentence[-1] in ".!?":
            issues.append("⚠️ Missing punctuation at end of sentence")

        # Check capitalization
        if sentence and sentence[0].islower():
            issues.append("⚠️ Sentence should start with a capital letter")

        if not issues:
            return (
                f"## ✅ Looks Good!\n\n"
                f"Your sentence passes basic checks: \"{sentence}\"\n\n"
                f"For a deeper analysis (style, nuance, alternatives), "
                f"connect an AI provider."
            )

        result = f"## 🔍 Grammar Check Results\n\n"
        result += f"**Sentence:** \"{sentence}\"\n\n"
        result += "### Issues Found:\n"
        for issue in issues:
            result += f"{issue}\n"
        if issues:
            result += f"\n### Corrected Version:\n{self._simple_correct(sentence, issues)}\n"
        return result

    @staticmethod
    def _simple_correct(sentence: str, issues: list) -> str:
        """Attempt simple corrections based on detected issues."""
        corrected = sentence
        for issue in issues:
            if "don't" in issue and "doesn't" in issue:
                corrected = re.sub(r'\b(he|she|it)\s+don\'t\b', r'\1 doesn\'t', corrected, flags=re.IGNORECASE)
                corrected = re.sub(r'\b(I|you|we|they)\s+doesn\'t\b', r'\1 don\'t', corrected, flags=re.IGNORECASE)
            if "a" in issue and "an" in issue and "before a vowel" in issue:
                corrected = re.sub(r'\ba\s+([aeiou])', r'an \1', corrected, flags=re.IGNORECASE)
            if "an" in issue and "a" in issue and "before a consonant" in issue:
                corrected = re.sub(r'\ban\s+([^aeiou\s])', r'a \1', corrected[:25], flags=re.IGNORECASE) + corrected[25:]
        if not corrected[-1] in ".!?":
            corrected += "."
        if corrected[0].islower():
            corrected = corrected[0].upper() + corrected[1:]
        return corrected

    @staticmethod
    def _get_help_text() -> str:
        """Get the help text for the language tutor plugin."""
        return (
            "## 🎓 Language Tutor Help\n\n"
            "**Commands:**\n\n"
            "### Configuration\n"
            "- `/tutor lang=en` — Set language (en/vi/ja/ko/zh/fr/de/es/it/pt/ru/th)\n"
            "- `/tutor lang=en level=B1` — Set CEFR level (A1-C2)\n"
            "- `/tutor lang=en mode=grammar` — Set mode (grammar/vocab/conversation/writing)\n"
            "- `/tutor lang=en native=vi` — Set your native language\n\n"
            "### Learning\n"
            "- `grammar: <sentence>` — Check grammar\n"
            "- `vocab: <word>` — Learn vocabulary\n"
            "- `practice: <topic>` — Conversation practice\n"
            "- `exercises` — Generate exercises\n\n"
            "**Supported Languages:** " + ", ".join(
                f"{code}={name}" for code, name in sorted(_LANGUAGE_NAMES.items())
            ) + "\n\n"
            "**Tip:** Connect an AI provider (OpenAI/Gemini/Ollama) for full AI-powered tutoring!"
        )
