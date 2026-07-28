"""
Content Moderation Filter (Feature 78)

Provides safety filtering for both user input and model output to detect
and flag content that violates community guidelines or is potentially harmful.

The filter uses keyword-based detection with pattern matching and category
classification. It can be configured to block, warn, or log violations.

Usage:
    from src.core.content_filter import ContentFilter, ModerationResult

    filter = ContentFilter()
    result = filter.check_input("What is the meaning of life?")
    if result.flagged:
        print(f"Flagged as: {result.categories}")
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger

logger = setup_logger("content_filter")


# ============================================================
# Moderation Result
# ============================================================


@dataclass
class ModerationResult:
    """Result of a content moderation check.

    Attributes:
        flagged: Whether any category was triggered
        categories: List of triggered category names
        reasons: List of specific reason strings for why it was flagged
        original_text: The text that was checked (truncated for logging)
        action: Recommended action: "allow", "warn", or "block"
    """

    flagged: bool = False
    categories: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    original_text: str = ""
    action: str = "allow"

    def to_dict(self) -> dict:
        return {
            "flagged": self.flagged,
            "categories": self.categories,
            "reasons": self.reasons,
            "action": self.action,
        }


# ============================================================
# Content Filter
# ============================================================


class ContentFilter:
    """Moderation filter for user input and AI responses.

    Uses keyword and pattern matching to detect potentially harmful content.
    Supports multiple categories with configurable severity levels.

    Categories:
      - harassment: Threats, bullying, hate speech
      - self_harm: Suicide, self-injury
      - violence: Violent content, weapons
      - illegal: Illegal activities, drugs
      - explicit: Explicit sexual content
      - spam: Spam, phishing, scams
    """

    # ── Category-specific patterns ──
    _PATTERNS: dict[str, list[tuple[str, str]]] = {
        "harassment": [
            (r"\b(?:đồ ngu|đồ điên|mày chết|mày ngu)\b", "InsuAlt/name-calling"),
            (r"\b(?:kill yoursel|hurt yoursel|you should die)\b", "Threat of harm"),
            (r"\b(?:chết đi|mày nên chết|tụi mày chết)\b", "Death threat"),
        ],
        "self_harm": [
            (r"\b(?:suicide|kill myse|end my life|take my own)\b", "Suicide reference"),
            (r"\b(?:tự tử|tự sát|tự vẫn|kết thúc cuộc đời)\b", "Suicide reference (VN)"),
            (r"\b(?:self-harm|self harm|cutting myse)\b", "Self-harm reference"),
        ],
        "violence": [
            (r"\b(?:bom|bomb|explosive|massacre|school shooting)\b", "Weapon/violence reference"),
            (r"\b(?:giết|sát hại|đánh bom|khủng bố)\b", "Violence reference (VN)"),
            (r"\b(?:mass shooting|shoot up|terrorist attack)\b", "Mass violence reference"),
        ],
        "illegal": [
            (r"\b(?:hack|hacking|crack|cracking|exploit)\b", "Hacking reference"),
            (r"\b(?:ma túy|heroin|cocaine|cần sa|meth)\b", "Drug reference (VN)"),
            (r"\b(?:cá độ|đánh bạc|tổ chức đánh bạc)\b", "Gambling reference"),
            (r"\b(?:make bom|c4|plastic explos|pipe bomb)\b", "Explosives instruction"),
        ],
        "explicit": [
            (r"\b(?:xxx|porn|adult content|nsfw)\b", "Explicit content label"),
            (r"\b(?:nội dung người lớn|18\+|sex|khiêu dâm)\b", "Explicit content (VN)"),
        ],
        "spam": [
            (r"\b(?:buy now|click here|limited offer|free money|congratulations you won)\b", "Spam/phishing pattern"),
            (r"\b(?:đầu tư|thu nhập thụ động|kiếm tiền nhanh|làm giàu không khó)\b", "Spam/scam pattern (VN)"),
            (r"https?://bit\.ly|https?://tinyurl|https?://shorturl", "URL shortener (spam risk)"),
        ],
    }

    def __init__(self, block_on: Optional[list[str]] = None, warn_on: Optional[list[str]] = None):
        """Initialize the content filter.

        Args:
            block_on: Categories that should result in "block" action.
                      Default: ["harassment", "self_harm", "violence", "illegal"]
            warn_on: Categories that should result in "warn" action.
                     Default: ["explicit", "spam"]
        """
        self._block_on = set(block_on or ["harassment", "self_harm", "violence", "illegal"])
        self._warn_on = set(warn_on or ["explicit", "spam"])
        self._total_checks = 0
        self._total_flagged = 0

        # Pre-compile patterns for performance
        self._compiled: dict[str, list[tuple[re.Pattern, str]]] = {}
        for category, patterns in self._PATTERNS.items():
            self._compiled[category] = [
                (re.compile(pattern, re.IGNORECASE), reason)
                for pattern, reason in patterns
            ]

        logger.info(
            f"ContentFilter initialized: block_on={self._block_on}, warn_on={self._warn_on}"
        )

    # ── Public API ──

    def check_input(self, text: str) -> ModerationResult:
        """Check user input for harmful content.

        Args:
            text: The user's input text to check

        Returns:
            ModerationResult with categories and recommended action
        """
        self._total_checks += 1
        result = self._check(text)

        if result.flagged:
            self._total_flagged += 1
            logger.info(
                f"Input flagged [{result.action}]: "
                f"categories={result.categories}, "
                f"reasons={result.reasons[:2]}"
            )

        return result

    def check_output(self, text: str) -> ModerationResult:
        """Check AI output for harmful content before displaying.

        Args:
            text: The model's response text to check

        Returns:
            ModerationResult with categories and recommended action
        """
        self._total_checks += 1
        result = self._check(text)

        if result.flagged:
            self._total_flagged += 1
            logger.warning(
                f"Output flagged [{result.action}]: "
                f"categories={result.categories}"
            )

        return result

    def get_stats(self) -> dict:
        """Get filter statistics."""
        return {
            "total_checks": self._total_checks,
            "total_flagged": self._total_flagged,
            "flag_rate_pct": round(
                (self._total_flagged / self._total_checks * 100), 2
            ) if self._total_checks > 0 else 0.0,
            "block_categories": list(self._block_on),
            "warn_categories": list(self._warn_on),
        }

    # ── Internal ──

    def _check(self, text: str) -> ModerationResult:
        """Run pattern matching against all categories.

        Args:
            text: Text to check

        Returns:
            ModerationResult
        """
        if not text or not text.strip():
            return ModerationResult()

        result = ModerationResult(original_text=text[:200])

        for category, patterns in self._compiled.items():
            for pattern, reason in patterns:
                match = pattern.search(text)
                if match:
                    result.flagged = True
                    if category not in result.categories:
                        result.categories.append(category)
                    result.reasons.append(reason)

        # Determine action
        if result.flagged:
            category_set = set(result.categories)
            if category_set & self._block_on:
                result.action = "block"
            elif category_set & self._warn_on:
                result.action = "warn"

        return result
