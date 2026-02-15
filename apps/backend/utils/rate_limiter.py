"""Thread-safe rate-limiting utilities.

Provides both a class-based and decorator-based interface for enforcing
minimum intervals between consecutive calls — primarily used to avoid
hitting external API rate limits (e.g. TradingView).

Example::

    @rate_limited(calls_per_second=2)
    def fetch_quote(symbol: str) -> dict:
        ...
"""

import time
from functools import wraps

class RateLimiter:
    """Enforces a maximum call frequency using ``time.sleep``.

    Args:
        calls_per_second: Maximum allowed calls per second.
    """

    def __init__(self, calls_per_second: int = 1):
        import threading
        self.calls_per_second = calls_per_second
        self.last_call_time = 0
        self.min_interval = 1.0 / calls_per_second
        self._lock = threading.Lock()

    def wait_if_needed(self) -> None:
        """Block until the minimum inter-call interval has elapsed."""
        with self._lock:
            current_time = time.time()
            elapsed = current_time - self.last_call_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_call_time = time.time()

def rate_limited(calls_per_second: int = 1):
    """Decorator that rate-limits the wrapped function.

    Args:
        calls_per_second: Maximum invocations per second.

    Returns:
        A decorator that inserts a ``time.sleep`` before each call
        when the rate would otherwise be exceeded.
    """
    limiter = RateLimiter(calls_per_second)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper
    return decorator 