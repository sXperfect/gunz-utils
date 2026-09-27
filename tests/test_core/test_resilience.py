from __future__ import annotations

import asyncio
import unittest

from gunz_utils.resilience import (
    AsyncBulkhead,
    AsyncCircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class TestCircuitBreaker(unittest.IsolatedAsyncioTestCase):
    async def test_opens_and_recovers(self) -> None:
        breaker = AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=0)

        async def fail() -> None:
            raise OSError("down")

        for _ in range(2):
            with self.assertRaises(OSError):
                await breaker.call(fail)

        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        async def recover() -> str:
            return "ok"

        self.assertEqual(await breaker.call(recover), "ok")
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    async def test_open_rejects_work(self) -> None:
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=60)

        async def fail() -> None:
            raise OSError("down")

        with self.assertRaises(OSError):
            await breaker.call(fail)
        with self.assertRaises(CircuitOpenError):
            await breaker.call(fail)


class TestBulkhead(unittest.IsolatedAsyncioTestCase):
    async def test_bounds_concurrency(self) -> None:
        bulkhead = AsyncBulkhead(2)
        active = 0
        peak = 0

        async def work() -> None:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001)
            active -= 1

        await asyncio.gather(*(bulkhead.run(work) for _ in range(8)))
        self.assertLessEqual(peak, 2)
        self.assertEqual(bulkhead.available, 2)

    async def test_acquisition_timeout(self) -> None:
        bulkhead = AsyncBulkhead(1)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def held() -> None:
            entered.set()
            await release.wait()

        holder = asyncio.create_task(bulkhead.run(held))
        await entered.wait()
        try:
            with self.assertRaisesRegex(TimeoutError, "bulkhead acquisition timed out"):
                await bulkhead.run(lambda: asyncio.sleep(0), timeout=0.001)
        finally:
            release.set()
            await holder
        self.assertEqual(bulkhead.available, 1)

    async def test_negative_timeout_is_rejected(self) -> None:
        bulkhead = AsyncBulkhead(1)
        with self.assertRaises(ValueError):
            await bulkhead.run(lambda: asyncio.sleep(0), timeout=-1)


if __name__ == "__main__":
    unittest.main()
