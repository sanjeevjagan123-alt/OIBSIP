"""Unit tests for TokenBucketRateLimiter."""

from __future__ import annotations

import unittest

from server.logic.rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter(unittest.TestCase):
    """Tests for the Token Bucket rate limiter."""

    def test_initial_burst_capacity(self) -> None:
        """Burst capacity allows initial burst of requests."""
        limiter = TokenBucketRateLimiter(rate_per_second=5.0, burst_capacity=10.0)
        for _ in range(10):
            self.assertTrue(limiter.allow_request())

    def test_exceeds_burst_capacity(self) -> None:
        """Request beyond burst capacity is rejected."""
        limiter = TokenBucketRateLimiter(rate_per_second=5.0, burst_capacity=10.0)
        for _ in range(10):
            limiter.allow_request()
        self.assertFalse(limiter.allow_request())

    def test_token_replenishment(self) -> None:
        """Tokens replenish over time based on rate_per_second."""
        current_time = 0.0
        limiter = TokenBucketRateLimiter(
            rate_per_second=5.0,
            burst_capacity=10.0,
            time_func=lambda: current_time,
        )
        # Drain all tokens
        for _ in range(10):
            limiter.allow_request()
        self.assertFalse(limiter.allow_request())

        # Advance time by 1 second → should replenish 5 tokens
        current_time = 1.0
        for _ in range(5):
            self.assertTrue(limiter.allow_request())
        # 6th request should fail
        self.assertFalse(limiter.allow_request())

    def test_tokens_do_not_exceed_burst_capacity(self) -> None:
        """Tokens never exceed burst capacity, even after long idle period."""
        current_time = 0.0
        limiter = TokenBucketRateLimiter(
            rate_per_second=5.0,
            burst_capacity=10.0,
            time_func=lambda: current_time,
        )
        # Advance time by 100 seconds (would be 500 tokens without cap)
        current_time = 100.0
        for _ in range(10):
            self.assertTrue(limiter.allow_request())
        self.assertFalse(limiter.allow_request())

    def test_single_token_replenish(self) -> None:
        """A fractional time advance replenishes partial tokens."""
        current_time = 0.0
        limiter = TokenBucketRateLimiter(
            rate_per_second=5.0,
            burst_capacity=10.0,
            time_func=lambda: current_time,
        )
        # Drain all tokens
        for _ in range(10):
            limiter.allow_request()

        # Advance 0.2 seconds → 1 token
        current_time = 0.2
        self.assertTrue(limiter.allow_request())
        self.assertFalse(limiter.allow_request())

    def test_rate_limiter_with_custom_rate(self) -> None:
        """Custom rate and burst values work correctly."""
        limiter = TokenBucketRateLimiter(rate_per_second=1.0, burst_capacity=3.0)
        for _ in range(3):
            self.assertTrue(limiter.allow_request())
        self.assertFalse(limiter.allow_request())


if __name__ == "__main__":
    unittest.main()
