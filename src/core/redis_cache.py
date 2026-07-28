"""
Redis Caching Tier Module (Feature 88)

Provides a Redis-backed cache as an alternative to the in-memory SimpleTTLCache.
When Redis is available, it provides a centralized cache that persists across
app restarts and can be shared between multiple instances.

Usage:
    from src.core.redis_cache import RedisCache

    cache = RedisCache(host="localhost", port=6379, db=0)
    cache.set("my_key", {"data": "value"}, ttl_seconds=300)
    value = cache.get("my_key")

    # Use as replacement for SimpleTTLCache
    from src.core.cache import SimpleTTLCache
    cache = RedisCache() if redis_available else SimpleTTLCache()
"""

import json
import os
import pickle
import time
from typing import Any, Optional

from src.core import setup_logger

logger = setup_logger("redis_cache")

# Try to import redis
_HAS_REDIS = False
try:
    import redis as redis_lib
    _HAS_REDIS = True
except ImportError:
    redis_lib = None  # type: ignore


class RedisCache:
    """Redis-backed cache with TTL support.

    Gracefully degrades to local in-memory cache if Redis is unavailable
    or if the redis library is not installed.

    Usage:
        cache = RedisCache()
        cache.set("key", "value, ttl_seconds=60")
        val = cache.get("key")
        cache.delete("key")
        stats = cache.get_stats()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: int = 0,
        password: Optional[str] = None,
        prefix: str = "atlas:cache:",
        default_ttl: int = 3600,
        fallback_max_size: int = 200,
    ):
        """Initialize Redis cache.

        Args:
            host: Redis host (default: env REDIS_HOST or "localhost")
            port: Redis port (default: env REDIS_PORT or 6379)
            db: Redis database number
            password: Redis password (default: env REDIS_PASSWORD)
            prefix: Key prefix for namespacing
            default_ttl: Default TTL in seconds
            fallback_max_size: Max entries for fallback cache
        """
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._client: Optional[Any] = None
        self._available = False
        self._hits = 0
        self._misses = 0
        self._sets = 0

        # Fallback in-memory cache when Redis is unavailable
        self._fallback: dict[str, tuple[float, Any]] = {}
        self._fallback_max = fallback_max_size

        # Try to connect to Redis
        if _HAS_REDIS:
            redis_host = host or os.environ.get("REDIS_HOST", "localhost")
            redis_port = port or int(os.environ.get("REDIS_PORT", "6379"))
            redis_password = password or os.environ.get("REDIS_PASSWORD", None)

            try:
                self._client = redis_lib.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=db,
                    password=redis_password or None,
                    decode_responses=False,
                    socket_timeout=2.0,
                    socket_connect_timeout=2.0,
                )
                # Test connection
                self._client.ping()
                self._available = True
                logger.info(
                    f"Redis cache connected: {redis_host}:{redis_port}/{db}"
                )
            except Exception as e:
                logger.warning(
                    f"Redis unavailable, using fallback cache: {e}"
                )
                self._client = None
        else:
            logger.info("redis-py not installed, using fallback in-memory cache")

    @property
    def available(self) -> bool:
        """Whether Redis is currently available."""
        return self._available

    def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value, or None if not found
        """
        prefixed = self._prefix + key

        if self._available and self._client:
            try:
                data = self._client.get(prefixed)
                if data is not None:
                    self._hits += 1
                    return pickle.loads(data)
                self._misses += 1
                return None
            except Exception:
                self._misses += 1
                return self._fallback_get(prefixed)

        return self._fallback_get(prefixed)

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache (must be picklable)
            ttl_seconds: TTL in seconds (default: class default)

        Returns:
            True if successful
        """
        prefixed = self._prefix + key
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        self._sets += 1

        if self._available and self._client:
            try:
                data = pickle.dumps(value)
                self._client.setex(prefixed, ttl, data)
                return True
            except Exception:
                self._fallback_set(prefixed, value, ttl)
                return True

        self._fallback_set(prefixed, value, ttl)
        return True

    def delete(self, key: str) -> bool:
        """Delete a key from the cache.

        Args:
            key: Cache key

        Returns:
            True if deleted
        """
        prefixed = self._prefix + key
        self._fallback.pop(prefixed, None)

        if self._available and self._client:
            try:
                return bool(self._client.delete(prefixed))
            except Exception:
                return False
        return False

    def clear(self) -> int:
        """Clear ALL cache entries with the configured prefix.

        Returns:
            Number of entries cleared
        """
        count = len(self._fallback)
        self._fallback.clear()

        if self._available and self._client:
            try:
                cursor = 0
                deleted = 0
                while True:
                    cursor, keys = self._client.scan(
                        cursor, match=f"{self._prefix}*", count=100
                    )
                    if keys:
                        deleted += self._client.delete(*keys)
                    if cursor == 0:
                        break
                count = max(count, deleted)
            except Exception:
                pass

        return count

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "available": self._available,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(self._hits / total * 100, 1) if total > 0 else 0.0,
            "sets": self._sets,
            "fallback_size": len(self._fallback),
            "fallback_max": self._fallback_max,
            "prefix": self._prefix,
            "default_ttl": self._default_ttl,
        }

    # ── Fallback (in-memory) ──

    def _fallback_get(self, key: str) -> Optional[Any]:
        """Get from in-memory fallback cache."""
        entry = self._fallback.get(key)
        if entry is None:
            self._misses += 1
            return None

        expiry, value = entry
        if expiry is not None and expiry < time.time():
            self._fallback.pop(key, None)
            self._misses += 1
            return None

        self._hits += 1
        return value

    def _fallback_set(self, key: str, value: Any, ttl: int) -> None:
        """Set in in-memory fallback cache."""
        # Evict oldest if at capacity
        if len(self._fallback) >= self._fallback_max:
            try:
                oldest = min(self._fallback.items(), key=lambda x: x[1][0])
                self._fallback.pop(oldest[0])
            except (ValueError, KeyError):
                pass

        expiry = time.time() + ttl if ttl > 0 else None
        self._fallback[key] = (expiry, value)
