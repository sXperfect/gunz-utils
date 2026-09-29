from __future__ import annotations

import asyncio
import unittest

try:
    import pytest

    pytestmark = pytest.mark.slow
except ImportError:
    pytest = None  # type: ignore[assignment]


from gunz_utils.cache import SingleFlight, ttl_cache
from gunz_utils.faults import FailAfter, FaultSequence
from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.resilience import AsyncBulkhead, AsyncCircuitBreaker, CircuitState
from gunz_utils.serialization import canonical_json


class TestCoreInvariants(unittest.TestCase):
    def test_canonical_json_is_deterministic(self) -> None:
        left = {"z": [3, 2, 1], "a": {"y": 2, "x": 1}}
        right = {"a": {"x": 1, "y": 2}, "z": [3, 2, 1]}
        self.assertEqual(canonical_json(left), canonical_json(right))

    def test_ttl_cache_never_exceeds_capacity(self) -> None:
        @ttl_cache(ttl=60, maxsize=3)
        def identity(value: int) -> int:
            return value

        for value in range(100):
            identity(value)
            self.assertLessEqual(identity.cache_info().size, 3)

    def test_fault_injectors_are_deterministic(self) -> None:
        fail = FailAfter(2, lambda: OSError("injected"))
        fail()
        fail()
        with self.assertRaises(OSError):
            fail()

        sequence = FaultSequence(frozenset({2, 4}))
        sequence.check(lambda: OSError())
        with self.assertRaises(OSError):
            sequence.check(lambda: OSError())


class TestAsyncInvariants(unittest.IsolatedAsyncioTestCase):
    async def test_singleflight_high_contention(self) -> None:
        flight = SingleFlight()
        calls = 0

        async def work() -> int:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.005)
            return 7

        values = await asyncio.gather(
            *(flight.run("key", work) for _ in range(100))
        )
        self.assertEqual(values, [7] * 100)
        self.assertEqual(calls, 1)

    async def test_bulkhead_restores_capacity_after_failure(self) -> None:
        bulkhead = AsyncBulkhead(2)

        async def fail() -> None:
            raise OSError("injected")

        for _ in range(20):
            with self.assertRaises(OSError):
                await bulkhead.run(fail)
            self.assertEqual(bulkhead.available, 2)

    async def test_rate_limiter_never_overdraws(self) -> None:
        limiter = AsyncRateLimiter(1, capacity=3)
        successes = [await limiter.try_acquire() for _ in range(10)]
        self.assertEqual(sum(successes), 3)

    async def test_breaker_filtered_errors_do_not_open(self) -> None:
        breaker = AsyncCircuitBreaker(
            failure_threshold=1,
            failure_predicate=lambda exc: isinstance(exc, OSError),
        )

        async def bad_input() -> None:
            raise ValueError("caller")

        for _ in range(20):
            with self.assertRaises(ValueError):
                await breaker.call(bad_input)
        self.assertEqual(breaker.state, CircuitState.CLOSED)


if __name__ == "__main__":
    unittest.main()
