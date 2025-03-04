"""Rate limiting utilities to prevent API abuse."""

import time
from functools import wraps

class RateLimiter:
    def __init__(self, calls_per_second=1):
        self.calls_per_second = calls_per_second
        self.last_call_time = 0
        self.min_interval = 1.0 / calls_per_second

    def wait_if_needed(self):
        current_time = time.time()
        elapsed = current_time - self.last_call_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            time.sleep(sleep_time)
            
        self.last_call_time = time.time()

def rate_limited(calls_per_second=1):
    """Decorator to rate limit function calls."""
    limiter = RateLimiter(calls_per_second)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper
    return decorator 