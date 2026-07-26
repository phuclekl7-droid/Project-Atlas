"""
Caching module: Simple thread-safe TTL cache for knowledge search and model responses.

Provides:
- SimpleTTLCache: Time-to-live cache with max size limit
- Works with any hashable keys
- Thread-safe (RLock) for Streamlit Cloud
- Stats tracking (hits, misses, size)
"""

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CacheEntry:
    """A single cache entry with expiration time."""

    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at


class SimpleTTLCache:
    """
    Thread-safe TTL cache with LRU-style eviction.

    Usage:
        cache = SimpleTTLCache(max_size=100, ttl_seconds=300)

        # Store
        cache.set("my_key", {"data": 42})

        # Retrieve
        value = cache.get("my_key")  # None if missing or expired

        # Check
        if "my_key" in cache:
            ...

        # Stats
        stats = cache.get_stats()
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of entries before eviction
            ttl_seconds: Time-to-live in seconds for each entry
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._data: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0

    # ── Core Operations ──

    def get(self, key: str) -> Any:
        """
        Get a value from the cache.

        Returns None if key is missing or entry has expired.
        Expired entries are automatically cleaned up.
        """
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.expired:
                del self._data[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store a value in the cache with current TTL."""
        with self._lock:
            # Evict if at capacity (LRU-style: remove oldest)
            if len(self._data) >= self.max_size and key not in self._data:
                self._evict_one()

            entry = CacheEntry(
                value=value,
                expires_at=time.time() + self.ttl_seconds,
            )
            self._data[key] = entry

    def delete(self, key: str) -> bool:
        """Remove a key from the cache. Returns True if existed."""
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all entries. Returns number of cleared entries."""
        with self._lock:
            count = len(self._data)
            self._data.clear()
            self._hits = 0
            self._misses = 0
            return count

    def __contains__(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return self.get(key) is not None

    # ── Maintenance ──

    def _evict_one(self) -> None:
        """Evict the oldest entry (LRU approximation)."""
        if not self._data:
            return
        # Find oldest entry by created_at
        oldest_key = min(self._data.keys(), key=lambda k: self._data[k].created_at)
        del self._data[oldest_key]

    def clean_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._data.items() if v.expires_at < now]
            for k in expired:
                del self._data[k]
            return len(expired)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(hit_rate, 1),
            }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"SimpleTTLCache("
            f"size={stats['size']}/{stats['max_size']}, "
            f"hit_rate={stats['hit_rate_pct']}%)"
        )


# ============================================================
# Cache Key Helpers
# ============================================================


def make_knowledge_cache_key(query: str, n_results: int = 3) -> str:
    """Generate a deterministic cache key for knowledge search queries."""
    normalized = query.lower().strip()
    raw = f"kb:{normalized}:{n_results}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def make_model_cache_key(
    prompt: str,
    context: Optional[list[dict]] = None,
    model_name: str = "",
) -> str:
    """Generate a deterministic cache key for model responses."""
    context_str = ""
    if context:
        context_str = "|".join(f"{m['role']}:{m['content'][:100]}" for m in context)
    raw = f"model:{model_name}:{prompt.strip()}:{context_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
