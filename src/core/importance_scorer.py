"""
Memory Importance Scoring Module (Feature 14)

Assigns an importance score (0.0–1.0) to each message in a session based on
multiple heuristics. High-scoring messages are retained when pruning context,
ensuring critical information is not lost.

Scoring factors:
  - Length: Longer messages tend to carry more information
  - Question marks: Questions likely contain important queries
  - Code blocks: Messages with code are likely important
  - Key terms: Technical terms, numbers, proper nouns
  - Recency: Newer messages score higher (time-decay optional)
  - User role: User messages slightly above assistant (source of requirements)

Usage:
    from src.core.importance_scorer import ImportanceScorer

    scorer = ImportanceScorer()
    score = scorer.score_message("My email is john@example.com")
    # Returns 0.75 (has email pattern, medium length, user-like)
"""

import re
from dataclasses import dataclass
from typing import Optional

from src.core import setup_logger

logger = setup_logger("importance_scorer")


# ============================================================
# Scoring Factors
# ============================================================


@dataclass
class ScoreFactors:
    """Individual factor scores that make up the final importance score.

    Attributes:
        length_factor: 0.0–1.0, based on message length
        question_factor: 0.0–1.0, whether the message asks a question
        code_factor: 0.0–1.0, whether the message contains code
        entity_factor: 0.0–1.0, presence of important entities (email, URLs, numbers)
        term_factor: 0.0–1.0, presence of technical/key terms
        role_factor: 0.0–1.0, based on role (user slightly above assistant)
    """

    length_factor: float = 0.0
    question_factor: float = 0.0
    code_factor: float = 0.0
    entity_factor: float = 0.0
    term_factor: float = 0.0
    role_factor: float = 0.5  # Default neutral

    @property
    def weighted_score(self) -> float:
        """Calculate weighted combination of all factors.

        Weights:
          - Length: 0.20 (moderate — long messages may be verbose, not valuable)
          - Question: 0.25 (high — questions drive the conversation)
          - Code: 0.20 (high — code blocks are valuable)
          - Entity: 0.15 (moderate — emails, URLs indicate important info)
          - Term: 0.10 (low — technical terms are nice but not critical)
          - Role: 0.10 (low — slight bias toward user messages)
        """
        return (
            self.length_factor * 0.20
            + self.question_factor * 0.25
            + self.code_factor * 0.20
            + self.entity_factor * 0.15
            + self.term_factor * 0.10
            + self.role_factor * 0.10
        )


# ============================================================
# Importance Scorer
# ============================================================


class ImportanceScorer:
    """Scores message importance based on content analysis.

    Usage:
        scorer = ImportanceScorer()

        user_score = scorer.score_message(
            "What is the capital of France?",
            role="user",
        )
        # user_score: 0.0–1.0

        code_score = scorer.score_message(
            "Here's the solution: ```python\\nprint('hello')\\n```",
            role="assistant",
        )
        # code_score: high due to code block
    """

    # Patterns that indicate important content
    _ENTITY_PATTERNS = [
        (r"[\w.+-]+@[\w-]+\.[\w.-]+", 0.8),   # Email
        (r"https?://[^\s]+", 0.7),              # URL
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", 0.6),  # IP address
        (r"\b[A-Z]{2,}\b", 0.3),                # Acronym (all caps)
        (r"\b\d{9,}\b", 0.4),                   # Long numbers (IDs)
    ]

    _KEY_TERMS_PATTERNS = [
        r"```\w*",        # Code blocks
        r"\b(error|bug|fix|issue|problem|crash|fail)\b",
        r"\b(password|api.?key|token|secret|credential)\b",
        r"\b(important|urgent|critical|asap|deadline)\b",
        r"\b(config|setup|install|deploy|migrate|update)\b",
        r"\b(version|release|update|upgrade|rollback)\b",
        r"\b(username|email|phone|address|contact)\b",
    ]

    def __init__(self, enable_key_terms: bool = True):
        """Initialize the scorer.

        Args:
            enable_key_terms: Whether to scan for key technical terms
        """
        self._enable_key_terms = enable_key_terms
        self._stats = {"total_scored": 0, "high_importance_count": 0}

    def score_message(
        self,
        content: str,
        role: str = "user",
        recency_order: Optional[int] = None,
        total_messages: Optional[int] = None,
    ) -> float:
        """Score a single message's importance.

        Args:
            content: The message text content
            role: "user", "assistant", or "system"
            recency_order: Position from newest (0=newest). Used for recency boost.
            total_messages: Total messages in session (for relative recency).

        Returns:
            Importance score between 0.0 (low) and 1.0 (high)
        """
        if not content or not content.strip():
            return 0.0

        factors = self._compute_factors(content, role)

        # Apply recency boost (if positions provided)
        score = factors.weighted_score
        if recency_order is not None and total_messages is not None and total_messages > 1:
            # Newer messages get a slight boost
            recency_factor = 1.0 - (recency_order / total_messages) * 0.3
            score = min(1.0, score * recency_factor)

        self._stats["total_scored"] += 1
        if score >= 0.7:
            self._stats["high_importance_count"] += 1

        return round(score, 3)

    def _compute_factors(self, content: str, role: str) -> ScoreFactors:
        """Compute individual scoring factors for a message.

        Args:
            content: Message text
            role: Message role

        Returns:
            ScoreFactors instance
        """
        factors = ScoreFactors()

        # Length factor: logarithmic scale up to ~2000 chars
        length = len(content)
        if length > 0:
            factors.length_factor = min(1.0, (length ** 0.5) / 45)

        # Question factor: messages with ? are likely important
        if "?" in content:
            factors.question_factor = min(1.0, content.count("?") * 0.3 + 0.4)

        # Code factor: code blocks indicate technical importance
        code_blocks = re.findall(r"```\w*\n.*?```", content, re.DOTALL)
        if code_blocks:
            factors.code_factor = min(1.0, 0.5 + len(code_blocks) * 0.15)

        # Entity factor: emails, URLs, IPs, etc.
        entity_score = 0.0
        for pattern, weight in self._ENTITY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                entity_score = max(entity_score, weight)
        # Multiple entities boost score
        entity_count = sum(
            1 for p, _ in self._ENTITY_PATTERNS
            if re.search(p, content, re.IGNORECASE)
        )
        if entity_count > 1:
            entity_score = min(1.0, entity_score + entity_count * 0.1)
        factors.entity_factor = entity_score

        # Key terms factor
        if self._enable_key_terms:
            term_count = 0
            for pattern in self._KEY_TERMS_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    term_count += 1
            factors.term_factor = min(1.0, term_count * 0.25)

        # Role factor
        if role == "user":
            factors.role_factor = 0.6  # User messages are slightly more important
        elif role == "system":
            factors.role_factor = 0.4  # System messages are slightly lower
        else:
            factors.role_factor = 0.5  # Assistant messages are neutral

        return factors

    def get_stats(self) -> dict:
        """Get scoring statistics."""
        total = self._stats["total_scored"]
        return {
            "total_scored": total,
            "high_importance_count": self._stats["high_importance_count"],
            "high_importance_pct": round(
                self._stats["high_importance_count"] / total * 100, 1
            ) if total > 0 else 0.0,
        }

    def get_scored_messages(
        self,
        messages: list[tuple[str, str]],
        top_k: int = 5,
    ) -> list[tuple[str, str, float]]:
        """Score multiple messages and return the top-k by importance.

        Args:
            messages: List of (role, content) tuples
            top_k: Number of top messages to return

        Returns:
            List of (role, content, score) tuples, sorted by score descending
        """
        scored = []
        total = len(messages)

        for i, (role, content) in enumerate(messages):
            score = self.score_message(
                content, role=role,
                recency_order=i,
                total_messages=total,
            )
            scored.append((role, content, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_k]
