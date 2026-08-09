"""Thread-safe Token Bucket Rate Limiter for request throughput control."""

from __future__ import annotations

import threading
import time
from typing import Callable


class TokenBucketRateLimiter:
    """Implements the Token Bucket algorithm for per-session rate limiting."""

    def __init__(
        self,
        rate_per_second: float = 5.0,
        burst_capacity: float = 10.0,
        time_func: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate_per_second = rate_per_second
        self.burst_capacity = burst_capacity
        self.tokens = burst_capacity
        self.time_func = time_func
        self.last_update = self.time_func()
        self._lock = threading.Lock()

    def allow_request(self) -> bool:
        """Check if a request is allowed and consume 1 token. Returns True if allowed."""
        with self._lock:
            now = self.time_func()
            elapsed = now - self.last_update
            self.last_update = now

            # Refill tokens based on elapsed time
            self.tokens = min(self.burst_capacity, self.tokens + elapsed * self.rate_per_second)

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False
