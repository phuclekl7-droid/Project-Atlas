"""
Time-decay Memory Filter Module (Feature 18)

Applies time-based decay to message importance scores. Older messages
receive progressively lower weights, enabling the system to prioritize
recent information while still retaining context from earlier messages.

Uses configurable decay functions:
  - Exponential: score * exp(-lambda * hours_old)
  - Linear: score * max(0, 1 - hours_old / half_life_hours)
  - Step: score if hours_old < threshold else 0

Usage:
    from src.core.time_decay import TimeDecayFilter

    filter = TimeDecayFilter(method="exponential", half_life_hours=24)
    adjusted = filter.apply(original_score=0.8, hours_old=6)
"""

import math
import time
from dataclasses import dataclass
from typing import Optional

from src.core import setup_logger

logger = setup_logger("time_decay")


# ============================================================
# Data Models
# ============================================================


@dataclass
class DecayResult:
    """Result of applying time decay to a score.

    Attributes:
        original_score: The score before decay
        decayed_score: The score after decay
        hours_old: Age of the item in hours
        decay_factor: Multiplier applied (0.0–1.0)
        method: Decay method used
    """

    original_score: float
    decayed_score: float
    hours_old: float
    decay_factor: float
    method: str

    @property
    def retained_pct(self) -> float:
        """Percentage of original score retained."""
        if self.original_score > 0:
            return round(self.decayed_score / self.original_score * 100, 1)
        return 0.0


# ============================================================
# Time-Decay Filter
# ============================================================


class TimeDecayFilter:
    """Applies time decay to importance scores.

    Supports multiple decay methods with configurable half-life.

    Usage:
        filter = TimeDecayFilter(method="exponential", half_life_hours=24)

        # Decay a single score
        result = filter.apply(0.8, hours_old=12)
        print(f"Score decayed: {result.original_score} → {result.decayed_score}")

        # Decay multiple items
        items = [
            {"score": 0.9, "timestamp": time.time() - 3600},  # 1 hour old
            {"score": 0.7, "timestamp": time.time() - 86400},  # 1 day old
        ]
        results = filter.apply_batch(items)
    """

    def __init__(
        self,
        method: str = "exponential",
        half_life_hours: float = 24.0,
        threshold_hours: Optional[float] = None,
    ):
        """Initialize the time-decay filter.

        Args:
            method: Decay function ("exponential", "linear", or "step")
            half_life_hours: Time after which score is halved (default: 24h)
            threshold_hours: For "step" method, hours after which score drops to 0
        """
        if method not in ("exponential", "linear", "step"):
            raise ValueError(f"Unknown decay method: {method}. Use: exponential, linear, step")

        self._method = method
        self._half_life = half_life_hours
        self._threshold = threshold_hours or half_life_hours * 2
        self._total_applied = 0

        logger.debug(
            f"TimeDecayFilter initialized: method={method}, "
            f"half_life={half_life_hours}h, threshold={self._threshold}h"
        )

    def apply(self, original_score: float, hours_old: float) -> DecayResult:
        """Apply time decay to a score.

        Args:
            original_score: The original importance score (0.0–1.0)
            hours_old: Age of the item in hours

        Returns:
            DecayResult with original, decayed score, and metadata
        """
        self._total_applied += 1

        if original_score <= 0 or hours_old <= 0:
            return DecayResult(
                original_score=original_score,
                decayed_score=original_score,
                hours_old=hours_old,
                decay_factor=1.0,
                method=self._method,
            )

        decay_factor = self._compute_factor(hours_old)
        decayed_score = round(original_score * decay_factor, 4)

        return DecayResult(
            original_score=original_score,
            decayed_score=decayed_score,
            hours_old=round(hours_old, 2),
            decay_factor=round(decay_factor, 4),
            method=self._method,
        )

    def apply_batch(
        self,
        items: list[dict],
        score_key: str = "score",
        timestamp_key: str = "timestamp",
    ) -> list[DecayResult]:
        """Apply time decay to a batch of items.

        Each item dict must have a score and a Unix timestamp.
        The timestamp is used to compute hours_old = (now - timestamp) / 3600.

        Args:
            items: List of dicts with score and timestamp fields
            score_key: Dict key for the score value
            timestamp_key: Dict key for the Unix timestamp

        Returns:
            List of DecayResult objects
        """
        now = time.time()
        results = []

        for item in items:
            score = item.get(score_key, 0.0)
            ts = item.get(timestamp_key, now)
            hours_old = max(0.0, (now - ts) / 3600)
            results.append(self.apply(score, hours_old))

        return results

    def get_stats(self) -> dict:
        """Get filter statistics."""
        return {
            "method": self._method,
            "half_life_hours": self._half_life,
            "threshold_hours": self._threshold,
            "total_applied": self._total_applied,
        }

    # ── Internal ──

    def _compute_factor(self, hours_old: float) -> float:
        """Compute the decay factor based on the configured method.

        Args:
            hours_old: Age in hours

        Returns:
            Decay factor between 0.0 and 1.0
        """
        if hours_old <= 0:
            return 1.0

        if self._method == "exponential":
            # score * exp(-ln(2) * hours / half_life)
            return math.exp(-math.log(2) * hours_old / self._half_life)

        elif self._method == "linear":
            # score * max(0, 1 - hours / half_life)
            return max(0.0, 1.0 - hours_old / self._half_life)

        elif self._method == "step":
            # score if hours < threshold else 0
            return 1.0 if hours_old < self._threshold else 0.0

        return 1.0
