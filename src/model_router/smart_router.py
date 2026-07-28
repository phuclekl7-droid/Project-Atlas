"""
Smart Router: Automatically selects the best provider based on prompt content.

Analyzes user input with keyword-based rules to route each message to the
most suitable provider (Ollama for code, OpenAI for creative, Gemini for analysis).

Usage:
    router = SmartRouter(settings)
    provider = router.route("Write a Python function")  # -> "ollama"
    provider = router.route("Write a poem about AI")    # -> "openai"
"""

from typing import Optional

from src.core import setup_logger
from src.settings import (
    PROVIDER_GEMINI,
    PROVIDER_MOCK,
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    Settings,
)

logger = setup_logger("smart_router")


# ── Routing Rules ──
# Each rule: (keywords, suggested_provider, weight)
# First match wins (highest weight within a category)

_CODING_KEYWORDS = [
    "code", "coding", "function", "class", "method", "variable",
    "python", "javascript", "typescript", "java", "c++", "rust", "go",
    "react", "vue", "angular", "node", "npm", "pip",
    "bug", "debug", "debugging", "error", "exception", "stack trace",
    "algorithm", "data structure", "sorting", "searching",
    "api", "endpoint", "rest", "graphql", "http",
    "sql", "query", "database", "migration",
    "git", "commit", "branch", "merge", "pull request",
    "terminal", "command", "shell", "bash", "docker",
    "refactor", "optimize", "performance", "memory leak",
    "unit test", "pytest", "jest", "mocha",
    "compiler", "interpreter", "syntax", "runtime",
    "oop", "functional programming", "design pattern",
    "async", "await", "promise", "callback",
    "deploy", "ci/cd", "pipeline", "devops",
    "framework", "library", "dependency", "package",
    "write a function", "implement a", "fix this code",
]

_CREATIVE_KEYWORDS = [
    "write", "poem", "poetry", "story", "short story", "novel",
    "essay", "article", "blog", "blog post", "newsletter",
    "creative", "creative writing", "fiction", "narrative",
    "lyrics", "song", "rap", "script", "screenplay",
    "dialogue", "conversation", "monologue",
    "describe", "imagine", "dream", "fantasy",
    "metaphor", "simile", "imagery", "symbolism",
    "brainstorm", "idea", "concept", "inspiration",
    "title", "headline", "tagline", "slogan",
    "copywriting", "ad copy", "marketing copy",
    "email", "newsletter", "campaign",
    "character", "world-building", "setting",
    "plot", "twist", "climax", "resolution",
    "write a poem", "tell me a story", "compose a",
]

_ANALYSIS_KEYWORDS = [
    "analyze", "analysis", "compare", "comparison", "contrast",
    "explain", "explanation", "define", "definition",
    "research", "investigate", "examine", "study",
    "summarize", "summary", "overview", "break down",
    "evaluate", "assessment", "review", "critique",
    "difference between", "similarities", "pros and cons",
    "what is", "how does", "why does", "what causes",
    "cause and effect", "correlation", "relationship",
    "interpret", "interpretation", "meaning of",
    "context", "background", "history of",
    "implication", "consequence", "significance",
    "theoretical", "framework", "paradigm",
    "methodology", "approach", "strategy",
    "case study", "evidence", "data shows",
    "synthesize", "integrate", "combine",
    "critically", "in-depth", "comprehensive",
    "explain like", "eli5", "in simple terms",
]

# Prompt length thresholds (characters)
_SHORT_PROMPT_MAX = 50      # Short questions -> Gemini (good at conciseness)
_LONG_PROMPT_MIN = 500       # Long prompts -> OpenAI (good at detailed responses)


class SmartRouter:
    """
    Analyzes prompts and recommends the best provider.

    Rules are keyword-based with three categories:
    - Coding → Ollama (fast, local, good for code generation)
    - Creative → OpenAI (strong at creative writing)
    - Analysis → Gemini (good at analytical responses)

    Falls back to the default provider if no rules match.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.default_provider = settings.model_provider

    def route(self, prompt: str) -> str:
        """
        Analyze a prompt and return the best provider name.

        Args:
            prompt: The user's input text

        Returns:
            Provider name string (ollama, openai, gemini, or default)
        """
        if not prompt or not prompt.strip():
            return self.default_provider

        prompt_lower = prompt.strip().lower()
        prompt_len = len(prompt_lower)

        # ── Check coding keywords ──
        score_coding = self._score_keywords(prompt_lower, _CODING_KEYWORDS)
        if score_coding >= 2:
            logger.debug(f"SmartRouter: coding score={score_coding} -> {PROVIDER_OLLAMA}")
            return PROVIDER_OLLAMA

        # ── Check creative keywords ──
        score_creative = self._score_keywords(prompt_lower, _CREATIVE_KEYWORDS)
        if score_creative >= 2:
            logger.debug(f"SmartRouter: creative score={score_creative} -> {PROVIDER_OPENAI}")
            return PROVIDER_OPENAI

        # ── Check analysis keywords ──
        score_analysis = self._score_keywords(prompt_lower, _ANALYSIS_KEYWORDS)
        if score_analysis >= 2:
            logger.debug(f"SmartRouter: analysis score={score_analysis} -> {PROVIDER_GEMINI}")
            return PROVIDER_GEMINI

        # ── Length-based heuristics ──
        if prompt_len <= _SHORT_PROMPT_MAX:
            # Very short prompts -> use default (likely Ollama for speed)
            return self.default_provider

        if prompt_len >= _LONG_PROMPT_MIN:
            # Long prompts -> Gemini (handles context well)
            return PROVIDER_GEMINI

        # ── Single keyword match (weaker signal) ──
        if score_coding == 1:
            return PROVIDER_OLLAMA
        if score_creative == 1:
            return PROVIDER_OPENAI
        if score_analysis == 1:
            return PROVIDER_GEMINI

        # ── Fallback ──
        return self.default_provider

    def route_with_reason(self, prompt: str) -> tuple[str, str]:
        """
        Analyze a prompt and return (provider_name, reason).

        Useful for UI display (showing why a provider was chosen).

        Args:
            prompt: The user's input text

        Returns:
            Tuple of (provider_name, reason_string)
        """
        if not prompt or not prompt.strip():
            return self.default_provider, "empty input"

        prompt_lower = prompt.strip().lower()
        prompt_len = len(prompt_lower)

        score_coding = self._score_keywords(prompt_lower, _CODING_KEYWORDS)
        if score_coding >= 2:
            return PROVIDER_OLLAMA, f"coding keywords detected (score={score_coding})"

        score_creative = self._score_keywords(prompt_lower, _CREATIVE_KEYWORDS)
        if score_creative >= 2:
            return PROVIDER_OPENAI, f"creative keywords detected (score={score_creative})"

        score_analysis = self._score_keywords(prompt_lower, _ANALYSIS_KEYWORDS)
        if score_analysis >= 2:
            return PROVIDER_GEMINI, f"analysis keywords detected (score={score_analysis})"

        if prompt_len <= _SHORT_PROMPT_MAX:
            return self.default_provider, f"short prompt ({prompt_len} chars)"

        if prompt_len >= _LONG_PROMPT_MIN:
            return PROVIDER_GEMINI, f"long prompt ({prompt_len} chars)"

        if score_coding == 1:
            return PROVIDER_OLLAMA, "single coding keyword match"
        if score_creative == 1:
            return PROVIDER_OPENAI, "single creative keyword match"
        if score_analysis == 1:
            return PROVIDER_GEMINI, "single analysis keyword match"

        return self.default_provider, "no specific keywords (default)"

    def _score_keywords(self, text: str, keywords: list[str]) -> int:
        """
        Count how many keywords from the list appear in the text.

        Multi-word keywords and single words are both supported.
        Returns a raw count (not weighted).
        """
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        return score

    def __repr__(self) -> str:
        return f"SmartRouter(default={self.default_provider!r})"
