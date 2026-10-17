# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
import unittest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.resilience import (
    AsyncBulkhead,
    AsyncCircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


class TestCircuitBreaker(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_configuration(self) -> None:
        for value in (0, -1, True):
            with self.subTest(failure_threshold=value):
                with self.assertRaises(ValueError):
                    AsyncCircuitBreaker(failure_threshold=value)

        for value in (math.nan, math.inf, -math.inf, True, -1.0):
            with self.subTest(recovery_timeout=value):
                with self.assertRaises(ValueError):
                    AsyncCircuitBreaker(recovery_timeout=value)

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

    async def test_half_open_probe_failure_predicate_exception_releases_flag(
        self,
    ) -> None:
        def predicate(
            exc: BaseException,
        ) -> bool:
            if isinstance(exc, ValueError):
                return True
            raise RuntimeError("predicate raised unexpected error")

        breaker = AsyncCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
            failure_predicate=predicate,
        )

        async def initial_failure() -> None:
            raise ValueError("first error")

        with self.assertRaises(ValueError):
            await breaker.call(initial_failure)

        self.assertEqual(breaker.state, CircuitState.OPEN)
        await asyncio.sleep(0.015)
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        async def probe_failure() -> None:
            raise TypeError("unexpected probe error")

        with self.assertRaises(RuntimeError) as cm:
            await breaker.call(probe_failure)

        self.assertIsInstance(cm.exception.__cause__, TypeError)

        await asyncio.sleep(0.015)
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        async def healthy() -> str:
            return "recovered"

        self.assertEqual(await breaker.call(healthy), "recovered")
        self.assertEqual(breaker.state, CircuitState.CLOSED)

    async def test_in_flight_success_does_not_close_open_circuit(self) -> None:
        breaker = AsyncCircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
        b_entered = asyncio.Event()
        b_can_finish = asyncio.Event()

        async def op_a() -> None:
            await b_entered.wait()
            raise ValueError("A failed")

        async def op_b() -> str:
            b_entered.set()
            await b_can_finish.wait()
            return "B succeeded"

        task_b = asyncio.create_task(breaker.call(op_b))
        await b_entered.wait()

        with self.assertRaises(ValueError):
            await breaker.call(op_a)

        self.assertEqual(breaker.state, CircuitState.OPEN)

        b_can_finish.set()
        res_b = await task_b
        self.assertEqual(res_b, "B succeeded")

        self.assertEqual(breaker.state, CircuitState.OPEN)

        async def op_new() -> str:
            return "new"

        with self.assertRaises(CircuitOpenError):
            await breaker.call(op_new)

    async def test_half_open_concurrent_probe_rejection(self) -> None:
        """In HALF_OPEN state, only 1 probe can run; others get CircuitOpenError."""
        breaker = AsyncCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.01,
        )

        async def init_fail() -> None:
            raise ValueError("down")

        with self.assertRaises(ValueError):
            await breaker.call(init_fail)

        self.assertEqual(breaker.state, CircuitState.OPEN)
        await asyncio.sleep(0.015)
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        probe_entered = asyncio.Event()
        probe_proceed = asyncio.Event()

        async def probe_op() -> str:
            probe_entered.set()
            await probe_proceed.wait()
            return "recovered"

        probe_task = asyncio.create_task(breaker.call(probe_op))
        await probe_entered.wait()

        #? While probe is in flight, concurrent caller must receive CircuitOpenError
        async def concurrent_op() -> str:
            return "should_not_run"

        with self.assertRaises(CircuitOpenError):
            await breaker.call(concurrent_op)

        probe_proceed.set()
        res = await probe_task
        self.assertEqual(res, "recovered")
        self.assertEqual(breaker.state, CircuitState.CLOSED)


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

    async def test_rejects_non_finite_timeout_and_boolean_limit(self) -> None:
        with self.assertRaises(ValueError):
            AsyncBulkhead(True)

        bulkhead = AsyncBulkhead(1)
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(timeout=value):
                with self.assertRaises(ValueError):
                    await bulkhead.run(
                        lambda: asyncio.sleep(0),
                        timeout=value,
                    )

    async def test_cancellation_releases_permit_during_execution(self) -> None:
        bulkhead = AsyncBulkhead(1)
        entered = asyncio.Event()

        async def hung_work() -> None:
            entered.set()
            await asyncio.sleep(100.0)

        task = asyncio.create_task(bulkhead.run(hung_work))
        await entered.wait()
        self.assertEqual(bulkhead.available, 0)

        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(bulkhead.available, 1)

    async def test_cancellation_releases_waiter_before_permit(self) -> None:
        bulkhead = AsyncBulkhead(1)
        entered = asyncio.Event()
        can_finish = asyncio.Event()

        async def holder_op() -> None:
            entered.set()
            await can_finish.wait()

        holder_task = asyncio.create_task(bulkhead.run(holder_op))
        await entered.wait()
        self.assertEqual(bulkhead.available, 0)

        async def waiter_op() -> None:
            pass

        waiter_task = asyncio.create_task(bulkhead.run(waiter_op))
        await asyncio.sleep(0.005)
        waiter_task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await waiter_task

        can_finish.set()
        await holder_task
        self.assertEqual(bulkhead.available, 1)


if __name__ == "__main__":
    unittest.main()
