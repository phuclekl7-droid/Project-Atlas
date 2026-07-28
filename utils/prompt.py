"""
Prompt Utilities: Auto-enhancement, streaming render fix, session tagging, and cost display.

Extracted from app.py to reduce its size.
"""

import logging
from typing import Optional


# ============================================================
# Session Tagging (Feature 16) — data moved from app.py
# ============================================================

SESSION_TAG_KEYWORDS = {
    "code": [
        "python", "javascript", "code", "function", "class", "def ", "import ", "const ",
        "var ", "return ", "print", "debug", "bug", "error", "exception", "compile",
        "syntax", "api", "endpoint", "json", "html", "css", "react", "vue", "node",
        "docker", "git", "commit", "branch", "pull", "merge", "deploy", "server",
        "database", "sql", "query", "script", "bash", "terminal", "command",
        "algorithm", "data structure", "array", "list", "dict", "loop", "async",
        "thread", "process", "memory", "performance", "optimize", "refactor",
    ],
    "question": [
        "?", "how to", "what is", "why does", "when should", "where can",
        "which one", "cách", "làm thế nào", "tại sao", "khi nào", "bao nhiêu",
    ],
    "creative": [
        "write", "story", "poem", "essay", "content", "article", "blog",
        "creative", "imagine", "design", "draw", "paint", "music", "song",
        "viết", "sáng tác", "thơ", "truyện", "kịch bản",
    ],
    "learning": [
        "learn", "study", "understand", "explain", "teach", "tutorial",
        "guide", "beginner", "advanced", "course", "lesson", "practice",
        "học", "bài học", "giải thích", "hướng dẫn", "luyện tập",
    ],
}

TAG_LABELS = {
    "code": "💻 Code",
    "question": "❓ Q&A",
    "creative": "🎨 Creative",
    "learning": "📚 Learning",
    "general": "💬 General",
}

TAG_CLASSES = {
    "code": "tag-coding",
    "question": "tag-question",
    "creative": "tag-creative",
    "learning": "tag-learning",
    "general": "tag-general",
}


def detect_session_tags(messages_content: list[str]) -> list[str]:
    """
    Detect conversation tags based on keyword matching in message content.

    Args:
        messages_content: List of message content strings to analyze

    Returns:
        List of tag names (e.g., ["code", "question"])
    """
    if not messages_content:
        return ["general"]

    combined = " ".join(messages_content).lower()

    detected = set()
    for tag, keywords in SESSION_TAG_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                detected.add(tag)
                break

    if not detected:
        detected.add("general")

    return list(detected)


def render_session_tags(tags: list[str]) -> str:
    """Render session tags as HTML badges."""
    if not tags:
        tags = ["general"]
    parts = []
    for tag in tags[:3]:
        class_name = TAG_CLASSES.get(tag, "tag-general")
        label = TAG_LABELS.get(tag, tag.capitalize())
        parts.append(f'<span class="session-tag {class_name}">{label}</span>')
    return " ".join(parts)


# ============================================================
# Smooth Streaming Render Fix
# ============================================================


def fix_streaming_render(text: str) -> str:
    """
    Fix unclosed markdown code blocks during streaming to prevent UI flickering.

    Works for:
    - Triple backticks: ```... (no closing)

    Args:
        text: Partial streaming text

    Returns:
        Text with temporary closing markers added
    """
    if not text:
        return text

    triple_count = text.count("```")
    if triple_count % 2 == 1:
        text = text + "\n```"

    return text


# ============================================================
# Auto Prompt Enhancer (Feature 67)
# ============================================================


def enhance_prompt(prompt: str) -> str:
    """
    Auto Prompt Enhancer: Rewrite vague/short prompts to be more explicit.
    """
    if not prompt or not prompt.strip():
        return prompt

    stripped = prompt.strip()
    word_count = len(stripped.split())

    if word_count < 5:
        lowered = stripped.lower()
        skip_words = {
            "hello", "hi", "hey", "thanks", "thank", "bye", "goodbye",
            "ok", "okay", "yes", "no", "yep", "nope", "sure", "great",
            "help", "info", "test", "clear", "reset",
        }
        if lowered.strip().rstrip("?.,!") in skip_words:
            return prompt

        enhanced = (
            f"{stripped}\n\n"
            f"[Note: Please provide a detailed and thorough response to the above. "
            f"If the query is brief, infer the most likely intent and elaborate.]"
        )
        logging.getLogger("app").info(
            f"Auto Prompt Enhancer: expanded '{stripped}' ({word_count} words)"
        )
        return enhanced

    return prompt


# ============================================================
# Token Cost Display Helper (Feature 157)
# ============================================================


def render_token_cost_html(response) -> str:
    """
    Return HTML string showing token usage and estimated cost.

    Used by both handlers/streaming.py (async mode) and ui/chat.py (streaming mode).
    Broken out to avoid circular imports.

    Args:
        response: A ModelResponse-like object with .tokens and .provider attributes

    Returns:
        HTML string (empty on error), ready for st.markdown(..., unsafe_allow_html=True)
    """
    try:
        tokens = getattr(response, "tokens", 0) or 0
        provider = getattr(response, "provider", "mock") or "mock"

        cost_rates = {
            "openai": 0.000015,
            "gemini": 0.000005,
            "ollama": 0.0,
            "mock": 0.0,
        }
        cost_per_token = cost_rates.get(provider, 0.0)
        estimated_cost = tokens * cost_per_token

        if estimated_cost > 0:
            cost_str = f"~${estimated_cost:.6f}"
        else:
            cost_str = "💚 Free (local)"

        return (
            f'<div style="font-size: 0.7rem; color: #666; text-align: right; '
            f'padding: 0.2rem 0.5rem; margin-top: -0.3rem;">'
            f'⚡ {tokens:,} tokens · {cost_str}'
            f'</div>'
        )
    except Exception:
        return ""
