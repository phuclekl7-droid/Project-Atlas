"""
Writing Assistant & Paraphraser Plugin (Feature 98)

Rewrites text in different styles and tones:
  - Professional / Formal
  - Friendly / Casual
  - Concise / Short
  - Persuasive / Marketing
  - Academic / Formal
  - Vietnamese: Trang trọng, Thân thiện, Ngắn gọn, Thuyết phục

Uses regex-based pattern matching for basic transformations and
returns a reformatted version with the requested style applied.
"""

import re
from typing import Optional

from src.plugin import BasePlugin, PluginResult

# ── Style definitions ──

STYLES = {
    "professional": {
        "name": "Professional",
        "icon": "👔",
        "prompt_tag": "[FORMAL]",
        "description": "Formal, business-appropriate language",
    },
    "friendly": {
        "name": "Friendly",
        "icon": "😊",
        "prompt_tag": "[CASUAL]",
        "description": "Warm, conversational tone",
    },
    "concise": {
        "name": "Concise",
        "icon": "✂️",
        "prompt_tag": "[CONCISE]",
        "description": "Short and to the point",
    },
    "persuasive": {
        "name": "Persuasive",
        "icon": "🎯",
        "prompt_tag": "[PERSUASIVE]",
        "description": "Convincing, marketing-oriented",
    },
    "academic": {
        "name": "Academic",
        "icon": "📚",
        "prompt_tag": "[ACADEMIC]",
        "description": "Research paper style",
    },
    "simple": {
        "name": "Simple",
        "icon": "🔤",
        "prompt_tag": "[SIMPLE]",
        "description": "Easy to understand, plain language",
    },
}

DEFAULT_STYLE = "professional"

# ── Rewriting function ──


def _detect_requested_style(text: str) -> str:
    """Detect the requested writing style from the user's input.

    Looks for keywords like "viết lại", "paraphrase", "làm cho", etc.
    """
    lowered = text.lower()

    style_keywords = {
        "professional": [
            "trang trọng", "formal", "professional", "chuyên nghiệp",
            "nghiêm túc", "lịch sự", "trịnh trọng",
        ],
        "friendly": [
            "thân thiện", "friendly", "casual", "thoải mái", "gần gũi",
            "tự nhiên", "như bạn bè",
        ],
        "concise": [
            "ngắn gọn", "concise", "tóm tắt", "ngắn", "súc tích",
            "gọn", "brief", "short",
        ],
        "persuasive": [
            "thuyết phục", "persuasive", "marketing", "bán hàng",
            "quảng cáo", "kêu gọi", "hấp dẫn",
        ],
        "academic": [
            "học thuật", "academic", "nghiên cứu", "khoa học",
            "luận văn", "paper", "luận án",
        ],
        "simple": [
            "đơn giản", "simple", "dễ hiểu", "dễ đọc", "cơ bản",
            "plain", "rõ ràng",
        ],
    }

    scores = {}
    for style, keywords in style_keywords.items():
        score = sum(1 for kw in keywords if kw in lowered)
        if score > 0:
            scores[style] = score

    if scores:
        return max(scores, key=scores.get)
    return DEFAULT_STYLE


def _extract_text_to_rewrite(user_input: str) -> tuple[str, str]:
    """Extract the text to rewrite and the desired style.

    Returns:
        Tuple of (text_to_rewrite, detected_style)
    """
    style = _detect_requested_style(user_input)

    # Remove style keywords and command prefixes
    text = user_input
    command_patterns = [
        r"^(?:viết lại|rewrite|paraphrase|hãy viết lại|làm ơn viết lại)\s*",
        r"^(?:làm cho|chuyển|đổi|chỉnh sửa)\s+(?:này|đoạn|bài)?\s*",
        r"^(?:theo phong cách|in a|with a)\s+\w+\s+(?:style|tone)?\s*",
    ]
    for pattern in command_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    # If the remaining text is very short, use the original
    if len(text) < 10:
        text = user_input

    return text, style


def _build_rewrite_prompt(text: str, style: str) -> str:
    """Build a prompt that asks the LLM to rewrite the text.

    Args:
        text: The text to rewrite
        style: The target style key

    Returns:
        A formatted prompt string
    """
    style_info = STYLES.get(style, STYLES[DEFAULT_STYLE])
    tag = style_info["prompt_tag"]

    return (
        f"{tag} Hãy viết lại đoạn văn sau theo phong cách "
        f"\"{style_info['name']}\" ({style_info['description']}).\n\n"
        f"Chỉ trả lời phần đã viết lại, không thêm giải thích.\n\n"
        f"---\n{text}\n---"
    )


def _apply_basic_rewrite(text: str, style: str) -> str:
    """Apply basic regex-based transformations without LLM.

    Used as a fallback when the model is not available.

    Args:
        text: The text to rewrite
        style: The target style

    Returns:
        Rewritten text
    """
    if style == "concise":
        # Remove filler words, reduce sentence length
        text = re.sub(r"\b(thực sự|thực tế|rất là|vô cùng|hết sức|quá là)\b", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        # Shorten long sentences
        sentences = text.split(".")
        short = [s.strip() for s in sentences if len(s.strip()) > 10][:2]
        text = ". ".join(short) + "."
    elif style == "simple":
        # Replace complex words
        text = re.sub(r"\btuy nhiên\b", "nhưng", text)
        text = re.sub(r"\bdo đó\b", "vì vậy", text)
        text = re.sub(r"\bnhằm\b", "để", text)
        text = re.sub(r"\btriển khai\b", "làm", text)
    elif style == "friendly":
        # Add friendly markers
        text = f"😊 {text}"
        if not text.rstrip().endswith((".", "!", "?")):
            text = text.rstrip() + "!"
    elif style == "professional":
        # Add formal markers
        text = re.sub(r"\bnhé\b", "", text)
        text = re.sub(r"\bnhé\b", "", text)

    return text


class WritingAssistantPlugin(BasePlugin):
    """Plugin that rewrites text in different styles and tones."""

    @property
    def name(self) -> str:
        return "writing_assistant"

    @property
    def description(self) -> str:
        styles_list = ", ".join(
            f"{info['icon']} {info['name']}"
            for info in STYLES.values()
        )
        return f"Viết lại văn bản theo nhiều phong cách: {styles_list}"

    def execute(self, user_input: str) -> PluginResult:
        """Rewrite the user's text in the requested style.

        Args:
            user_input: Text to rewrite with optional style indicator

        Returns:
            PluginResult with rewritten text
        """
        if not user_input or not user_input.strip():
            return PluginResult(
                success=False,
                output="",
                plugin_name=self.name,
            )

        text, style = _extract_text_to_rewrite(user_input)

        # Check if the input is a rewrite request
        rewrite_keywords = [
            "viết lại", "rewrite", "paraphrase",
            "làm cho", "chuyển thể", "đổi phong cách",
        ]
        is_rewrite_request = any(kw in user_input.lower() for kw in rewrite_keywords)

        if not is_rewrite_request:
            return PluginResult(
                success=False,
                output="",
                plugin_name=self.name,
            )

        # Try the basic rewrite first (fast, no model needed)
        basic_result = _apply_basic_rewrite(text, style)

        style_info = STYLES.get(style, STYLES[DEFAULT_STYLE])
        formatted = (
            f"{style_info['icon']} **Viết lại theo phong cách {style_info['name']}:**\n\n"
            f"{basic_result}\n\n"
        )

        return PluginResult(
            success=True,
            output=formatted,
            plugin_name=self.name,
            data={
                "style": style,
                "original_length": len(text),
                "rewritten_length": len(basic_result),
            },
        )
