"""Thread-safe persistent JSON cache with TTL expiry.

Provides a simple key-value store backed by a JSON file on disk.
Writes are atomic (via ``tempfile`` + ``os.replace``) so concurrent
readers never see a partial file.  A threading lock protects in-memory
state.

Typical usage::

    cache = PersistentCache("results.json", expiry_seconds=3600)
    cache.set("analysis", {"score": 42})
    cache.get("analysis")   # → {"score": 42}
    cache.reload()           # re-read from disk (cross-process sync)
"""

import json
import os
import tempfile
import time
import threading
import logging

class PersistentCache:
    """Thread-safe JSON cache with TTL expiry and atomic disk writes.

    Args:
        cache_file: Path to the JSON file backing the cache.
        initial_data: Pre-loaded dict to use instead of reading from disk.
        expiry_seconds: Default time-to-live for cache entries (seconds).
    """

    def __init__(self, cache_file: str = "cache.json", initial_data: dict | None = None, expiry_seconds: int = 3600):
        self.cache_file = cache_file
        self.expiry_seconds = expiry_seconds
        self._lock = threading.Lock()
        self.cache = initial_data or self._load_cache()
        
        # Save cache immediately if initial data was provided
        if initial_data:
            self._save_cache()
    
    def _load_cache(self) -> dict:
        """Load cache from disk, returning an empty dict on failure."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading cache: {e}")
                return {}
        return {}
    
    def _save_cache(self) -> bool:
        """Persist cache to disk via atomic write (tempfile → os.replace).

        Returns:
            True on success, False if an error occurred.
        """
        try:
            cache_dir = os.path.dirname(self.cache_file) or "."
            os.makedirs(cache_dir, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=cache_dir, suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.cache, f)
                os.replace(tmp_path, self.cache_file)
            except BaseException:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
            return True
        except Exception as e:
            logging.error(f"Error saving cache: {e}")
            return False
    
    def get(self, key: str) -> object | None:
        """Retrieve a value if present and not expired.

        Args:
            key: Cache key (converted to string internally for JSON compat).

        Returns:
            The cached value, or ``None`` if missing / expired.
        """
        str_key = str(key)  # Convert tuple to string for JSON
        with self._lock:
            if str_key in self.cache:
                entry = self.cache[str_key]
                if time.time() - entry["timestamp"] < self.expiry_seconds:
                    return entry["data"]
        return None
    
    def set(self, key: str, value: object, expiry_seconds: int | None = None) -> None:
        """Store a value with the current timestamp.

        Args:
            key: Cache key.
            value: JSON-serialisable value.
            expiry_seconds: Unused — reserved for future per-key TTL.
        """
        str_key = str(key)  # Convert tuple to string for JSON
        with self._lock:
            self.cache[str_key] = {
                "data": value,
                "timestamp": time.time()
            }
        self._save_cache()
    
    def clear_expired(self) -> None:
        """Remove all entries whose TTL has elapsed and persist the result."""
        current_time = time.time()
        expired_keys = []

        with self._lock:
            for key, entry in list(self.cache.items()):
                if current_time - entry["timestamp"] > self.expiry_seconds:
                    expired_keys.append(key)

            for key in expired_keys:
                del self.cache[key]
        
        if expired_keys:
            self._save_cache()
            logging.info(f"Cleared {len(expired_keys)} expired cache entries")

    def reload(self) -> None:
        """Re-read the cache file from disk.

        Call this to pick up writes made by another process (e.g. the
        analysis subprocess writing results that the Flask API needs
        to serve).
        """
        with self._lock:
            self.cache = self._load_cache()

    def clear(self) -> None:
        """Delete all entries from memory and disk."""
        with self._lock:
            self.cache = {}
        self._save_cache() 