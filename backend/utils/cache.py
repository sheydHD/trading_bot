"""Persistent cache implementation."""

import json
import os
import time
import logging

class PersistentCache:
    """A simple cache that persists to disk."""
    
    def __init__(self, cache_file="cache.json", initial_data=None, expiry_seconds=3600):
        self.cache_file = cache_file
        self.expiry_seconds = expiry_seconds
        self.cache = initial_data or self._load_cache()
        
        # Save cache immediately if initial data was provided
        if initial_data:
            self._save_cache()
    
    def _load_cache(self):
        """Load cache from file if it exists."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading cache: {e}")
                return {}
        return {}
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
            return True
        except Exception as e:
            logging.error(f"Error saving cache: {e}")
            return False
    
    def get(self, key):
        """Get value from cache if it exists and is not expired."""
        str_key = str(key)  # Convert tuple to string for JSON
        if str_key in self.cache:
            entry = self.cache[str_key]
            if time.time() - entry["timestamp"] < self.expiry_seconds:
                return entry["data"]
        return None
    
    def set(self, key, value, expiry_seconds=None):
        """Set value in cache with current timestamp."""
        str_key = str(key)  # Convert tuple to string for JSON
        self.cache[str_key] = {
            "data": value,
            "timestamp": time.time()
        }
        self._save_cache()
    
    def clear_expired(self):
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if current_time - entry["timestamp"] > self.expiry_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            self._save_cache()
            logging.info(f"Cleared {len(expired_keys)} expired cache entries")

    def clear(self):
        """Clear the cache."""
        self.cache = {}
        self._save_cache() 