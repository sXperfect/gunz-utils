"""Tests for Wave 2: Async, leases, pipeline, rate limit, context, resilience, and concurrency."""

from __future__ import annotations

import asyncio
import math
import sys
import time
from typing import Any
import unittest

from gunz_utils.async_utils import cancel_and_wait, with_timeout
from gunz_utils.concurrency import (
    map_concurrent,
    map_unordered,
    process_imap,
    process_map,
)
from gunz_utils.context import (
    correlation_id,
    ensure_correlation_id,
    operation_context,
    reset_correlation_id,
    set_correlation_id,
)
from gunz_utils.leases import LeaseTiming, run_with_lease_heartbeat
from gunz_utils.pipeline import worker_map
from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.resilience import (
    AsyncBulkhead,
    AsyncCircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class TestAsyncUtilsWave2(unittest.IsolatedAsyncioTestCase):
    async def test_with_timeout_closes_coro_on_bad_timeout(self) -> None:
        closed = False

        async def coro() -> None:
            nonlocal closed
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                closed = True
                raise

        c = coro()
        with self.assertRaises(ValueError):
            await with_timeout(c, timeout=-1.0)
        # Verify the coroutine was closed (c.cr_frame is None when closed)
        self.assertIsNone(c.cr_frame)

    async def test_cancel_and_wait_validation(self) -> None:
        with self.assertRaises(TypeError):
            await cancel_and_wait("not_a_task")  # type: ignore[arg-type]


class TestLeasesWave2(unittest.IsolatedAsyncioTestCase):
    async def test_run_with_lease_heartbeat_custom_timing(self) -> None:
        timing = LeaseTiming(lease_seconds=10.0, heartbeat_interval=2.0)
        heartbeats: list[str] = []

        async def heartbeat() -> bool:
            heartbeats.append("beat")
            return True

        async def op() -> str:
            await asyncio.sleep(0.01)
            return "ok"

        res = await run_with_lease_heartbeat(
            renew=heartbeat,
            operation=op,
            timing=timing,
            renew_immediately=True,
        )
        self.assertEqual(res, "ok")
        self.assertGreater(len(heartbeats), 0)


class TestPipelineWave2(unittest.IsolatedAsyncioTestCase):
    async def test_worker_map_validation(self) -> None:
        with self.assertRaises(TypeError):
            await anext(worker_map("not_callable", [1, 2], workers=2))  # type: ignore[arg-type]

        async def dummy(x: int) -> int:
            return x

        with self.assertRaises(ValueError):
            await anext(worker_map(dummy, [1, 2], workers=0))

        with self.assertRaises(TypeError):
            await anext(worker_map(dummy, 123, workers=2))  # type: ignore[arg-type]

    async def test_worker_map_async_iterable(self) -> None:
        async def async_gen():
            for i in range(5):
                await asyncio.sleep(0.001)
                yield i

        async def double(x: int) -> int:
            return x * 2

        results: list[int] = []
        async for r in worker_map(double, async_gen(), workers=2):
            results.append(r)
        self.assertEqual(sorted(results), [0, 2, 4, 6, 8])


class TestRateLimiterWave2(unittest.IsolatedAsyncioTestCase):
    async def test_injectable_clock_and_jitter(self) -> None:
        current_time = 100.0

        def mock_clock() -> float:
            return current_time

        limiter = AsyncRateLimiter(rate=10.0, capacity=10.0, clock=mock_clock)
        self.assertEqual(limiter.available_tokens, 10.0)

        # Time going backwards should clamp elapsed to 0
        current_time = 50.0
        self.assertEqual(limiter.available_tokens, 10.0)

        # Invalid clock
        with self.assertRaises(TypeError):
            AsyncRateLimiter(rate=1.0, clock="not_callable")  # type: ignore[arg-type]

    async def test_overflow_guard(self) -> None:
        limiter = AsyncRateLimiter(rate=10.0)
        with self.assertRaises((ValueError, OverflowError)):
            await limiter.acquire(timeout=float("inf"))


class TestContextWave2(unittest.TestCase):
    def test_set_and_reset_correlation_id(self) -> None:
        old = correlation_id()
        token = set_correlation_id("test-corr-123")
        self.assertEqual(correlation_id(), "test-corr-123")
        reset_correlation_id(token)
        self.assertEqual(correlation_id(), old)

        with self.assertRaises(TypeError):
            set_correlation_id(12345)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            reset_correlation_id("not_a_token")  # type: ignore[arg-type]

    def test_operation_context_validation_and_whitespace(self) -> None:
        with self.assertRaises(TypeError):
            with operation_context(12345):  # type: ignore[arg-type]
                pass

        with operation_context("   ") as cid:
            self.assertTrue(len(cid) > 10)
            self.assertNotEqual(cid, "   ")


class TestResilienceWave2(unittest.IsolatedAsyncioTestCase):
    async def test_circuit_breaker_context_manager_and_failure_count(self) -> None:
        breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=1.0)
        self.assertEqual(breaker.failure_count, 0)

        with self.assertRaises(ValueError):
            async with breaker:
                raise ValueError("boom")

        self.assertEqual(breaker.failure_count, 1)

        with self.assertRaises(ValueError):
            async with breaker:
                raise ValueError("boom 2")

        self.assertEqual(breaker.failure_count, 2)
        self.assertEqual(breaker.state, CircuitState.OPEN)

        with self.assertRaises(CircuitOpenError):
            async with breaker:
                pass

    async def test_bulkhead_properties_and_context_manager(self) -> None:
        bulkhead = AsyncBulkhead(limit=2)
        self.assertEqual(bulkhead.active_count, 0)
        self.assertEqual(bulkhead.available_slots, 2)

        async with bulkhead:
            self.assertEqual(bulkhead.active_count, 1)
            self.assertEqual(bulkhead.available_slots, 1)

        self.assertEqual(bulkhead.active_count, 0)
        self.assertEqual(bulkhead.available_slots, 2)


class TestConcurrencyWave2(unittest.IsolatedAsyncioTestCase):
    def test_concurrency_eager_callable_validation(self) -> None:
        with self.assertRaises(TypeError):
            process_map("not_a_func", [1, 2])  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            process_imap("not_a_func", [1, 2])  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            map_unordered("not_a_func", [1, 2], limit=2)  # type: ignore[arg-type]

    async def test_map_concurrent_eager_validation(self) -> None:
        with self.assertRaises(TypeError):
            await map_concurrent("not_a_func", [1, 2], limit=2)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
