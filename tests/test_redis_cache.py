"""Tests for Redis Cache (Feature 88)."""

import time
import pytest
from src.core.redis_cache import RedisCache


class TestRedisCacheFallback:
    """Test RedisCache with fallback (no actual Redis)."""

    def test_initial_state(self):
        cache = RedisCache(host="127.0.0.1", port=16379)  # Wrong port
        assert cache.available is False
        stats = cache.get_stats()
        assert stats["available"] is False

    def test_set_and_get(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        assert result == "test_value"

    def test_get_nonexistent(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        result = cache.get("nonexistent_key")
        assert result is None

    def test_set_different_types(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        cache.set("str", "hello")
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"key": "value"})
        assert cache.get("str") == "hello"
        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"key": "value"}

    def test_ttl_expires(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        cache.set("expires_soon", "value", ttl_seconds=1)
        assert cache.get("expires_soon") == "value"
        time.sleep(1.1)
        assert cache.get("expires_soon") is None

    def test_delete(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        cache.set("delete_me", "value")
        assert cache.get("delete_me") is not None
        cache.delete("delete_me")
        assert cache.get("delete_me") is None

    def test_clear(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        cache.set("key1", "val1")
        cache.set("key2", "val2")
        cleared = cache.clear()
        assert cleared >= 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_stats(self):
        cache = RedisCache(host="127.0.0.1", port=16379)
        cache.set("stat_key", "value")
        cache.get("stat_key")
        cache.get("missing_key")
        stats = cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["sets"] >= 1

    def test_prefix_isolation(self):
        cache1 = RedisCache(host="127.0.0.1", port=16379, prefix="cache1:")
        cache2 = RedisCache(host="127.0.0.1", port=16379, prefix="cache2:")
        cache1.set("same_key", "value1")
        cache2.set("same_key", "value2")
        assert cache1.get("same_key") == "value1"
        assert cache2.get("same_key") == "value2"
