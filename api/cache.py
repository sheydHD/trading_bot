"""Enhanced persistent cache for API data."""

import os
import json
import time
from datetime import datetime

class PersistentCache:
    """A cache that persists to disk with improved reliability."""
    
    def __init__(self, cache_file="analysis_cache.json", initial_data=None, expiry_seconds=86400):
        self.cache_file = cache_file
        self.expiry_seconds = expiry_seconds
        self.cache = initial_data or self._load_cache()
        
        # Save cache immediately if initial data was provided
        if initial_data:
            self._save_cache()
    
    def _load_cache(self):
        """Load cache from file."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    print(f"Successfully loaded cache with {len(data.keys() if isinstance(data, dict) else data)} entries")
                    return data
        except Exception as e:
            print(f"Error loading cache: {e}")
        return {}
    
    def _save_cache(self):
        """Save cache to file."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f)
            print(f"Successfully saved cache to {self.cache_file}")
            return True
        except Exception as e:
            print(f"Error saving cache: {e}")
            return False
    
    def get(self, key):
        """Get value from cache."""
        if key in self.cache and isinstance(self.cache[key], dict):
            entry = self.cache[key]
            # Check if entry has timestamp and is not expired
            if 'timestamp' in entry and 'data' in entry:
                if time.time() - entry['timestamp'] < self.expiry_seconds:
                    print(f"Cache hit for {key} (age: {(time.time() - entry['timestamp'])/60:.1f} minutes)")
                    return entry['data']
                else:
                    print(f"Cache expired for {key}")
            else:
                # Legacy format without timestamp
                print(f"Cache hit for {key} (legacy format)")
                return entry
        return None
    
    def set(self, key, value, expiry_seconds=None):
        """Set value in cache."""
        expiry = expiry_seconds if expiry_seconds is not None else self.expiry_seconds
        self.cache[key] = {
            'timestamp': time.time(),
            'data': value,
            'expiry': expiry
        }
        print(f"Added {key} to cache with expiry {expiry} seconds")
        # Save immediately for reliability
        return self._save_cache()
    
    def clear(self):
        """Clear cache."""
        self.cache = {}
        return self._save_cache() 