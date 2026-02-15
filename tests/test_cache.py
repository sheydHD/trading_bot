"""Tests for PersistentCache."""

import json
import time
import pytest

from apps.backend.utils.cache import PersistentCache


class TestPersistentCache:
    """Unit tests for PersistentCache."""

    def test_set_and_get(self, tmp_cache_file):
        cache = PersistentCache(cache_file=tmp_cache_file, expiry_seconds=60)
        cache.set("key1", {"value": 42})
        assert cache.get("key1") == {"value": 42}

    def test_get_missing_key_returns_none(self, tmp_cache_file):
        cache = PersistentCache(cache_file=tmp_cache_file)
        assert cache.get("nonexistent") is None

    def test_expiry(self, tmp_cache_file):
        cache = PersistentCache(cache_file=tmp_cache_file, expiry_seconds=1)
        cache.set("ephemeral", "data")
        assert cache.get("ephemeral") == "data"
        time.sleep(1.1)
        assert cache.get("ephemeral") is None

    def test_persistence_to_disk(self, tmp_cache_file):
        cache1 = PersistentCache(cache_file=tmp_cache_file, expiry_seconds=300)
        cache1.set("persist", [1, 2, 3])

        # Create a brand-new cache instance from the same file
        cache2 = PersistentCache(cache_file=tmp_cache_file, expiry_seconds=300)
        assert cache2.get("persist") == [1, 2, 3]

    def test_clear(self, tmp_cache_file):
        cache = PersistentCache(cache_file=tmp_cache_file)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_clear_expired(self, tmp_cache_file):
        cache = PersistentCache(cache_file=tmp_cache_file, expiry_seconds=1)
        cache.set("old", "stale")
        time.sleep(1.1)
        cache.set("new", "fresh")
        cache.clear_expired()
        assert cache.get("old") is None
        assert cache.get("new") == "fresh"

    def test_atomic_write(self, tmp_cache_file):
        """Verify no .tmp file is left behind after write."""
        cache = PersistentCache(cache_file=tmp_cache_file)
        cache.set("k", "v")
        import os
        assert not os.path.exists(tmp_cache_file + ".tmp")

    def test_initial_data(self, tmp_cache_file):
        initial = {"preloaded": {"data": "hello", "timestamp": time.time()}}
        cache = PersistentCache(cache_file=tmp_cache_file, initial_data=initial)
        assert cache.get("preloaded") == "hello"
