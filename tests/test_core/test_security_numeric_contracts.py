"""Security regression tests for numeric resource/budget validation."""

from __future__ import annotations

import math
import unittest

from gunz_utils.cache import async_ttl_cache, ttl_cache
from gunz_utils.limits import Limits, ResourceBudget
from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.resilience import AsyncBulkhead, AsyncCircuitBreaker
from gunz_utils.retry import RetryPolicy, retry
from gunz_utils.upstream_protocol import PolicyUpstream


class _Upstream:
    name = "test"

    async def call(self, tool_name, arguments):
        return {}

    async def health_check(self):
        return True

    async def close(self):
        return None


class TestFiniteNumericContracts(unittest.TestCase):
    def test_cache_rejects_non_finite_or_non_integer_bounds(self) -> None:
        for ttl in (math.nan, math.inf, -math.inf, True):
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValueError):
                    ttl_cache(ttl=ttl)
                with self.assertRaises(ValueError):
                    async_ttl_cache(ttl=ttl)
        for maxsize in (math.inf, math.nan, True, 1.5):
            with self.subTest(maxsize=maxsize):
                with self.assertRaises(ValueError):
                    ttl_cache(ttl=1, maxsize=maxsize)

    def test_limits_reject_non_finite_and_wrong_types(self) -> None:
        for timeout in (math.nan, math.inf, -math.inf, True):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    Limits(timeout=timeout)
        for value in (True, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Limits(max_bytes=value)
        budget = ResourceBudget(max_bytes=10)
        with self.assertRaises(ValueError):
            budget.consume_bytes(True)

    def test_retry_rejects_non_finite_timing(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    RetryPolicy(base_delay=value)
                with self.assertRaises(ValueError):
                    retry(base_delay=value)
        with self.assertRaises(ValueError):
            RetryPolicy(attempts=True)

    def test_retry_delay_saturates_without_huge_integer_growth(self) -> None:
        policy = RetryPolicy(
            attempts=1,
            base_delay=1e-300,
            max_delay=10.0,
            jitter=False,
        )
        self.assertEqual(policy.delay(10**9), 10.0)

    def test_resilience_rejects_non_finite_timing_and_boolean_counts(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AsyncCircuitBreaker(recovery_timeout=value)
        with self.assertRaises(ValueError):
            AsyncCircuitBreaker(failure_threshold=True)
        with self.assertRaises(ValueError):
            AsyncBulkhead(True)

    def test_upstream_policy_rejects_non_finite_or_boolean_limits(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    PolicyUpstream(_Upstream(), timeout_seconds=value)
        with self.assertRaises(ValueError):
            PolicyUpstream(_Upstream(), max_concurrency=True)
        with self.assertRaises(ValueError):
            PolicyUpstream(_Upstream(), max_attempts=True)


class TestAsyncFiniteNumericContracts(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limiter_rejects_nan_and_infinity(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    AsyncRateLimiter(value)

        limiter = AsyncRateLimiter(10, capacity=2)
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(tokens=value):
                with self.assertRaises(ValueError):
                    await limiter.try_acquire(value)
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    await limiter.acquire(timeout=value)


if __name__ == "__main__":
    unittest.main()
