from __future__ import annotations

import asyncio
import gc
import unittest
from typing import Any

from gunz_utils.concurrency import gather_limited, map_concurrent, map_unordered


class TestConcurrency(unittest.IsolatedAsyncioTestCase):
    async def test_map_preserves_order_and_limit(self) -> None:
        active = 0
        peak = 0

        async def work(value: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.001)
            active -= 1
            return value * 2

        self.assertEqual(
            await map_concurrent(work, range(6), limit=2),
            [0, 2, 4, 6, 8, 10],
        )
        self.assertLessEqual(peak, 2)

    async def test_return_exceptions(self) -> None:
        async def fail() -> int:
            raise ValueError("x")

        result = await gather_limited([fail()], limit=1, return_exceptions=True)
        self.assertIsInstance(result[0], ValueError)

    async def test_return_exceptions_does_not_swallow_cancellation(self) -> None:
        async def cancel() -> int:
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await gather_limited(
                [cancel()],
                limit=1,
                return_exceptions=True,
            )

    async def test_invalid_limit(self) -> None:
        with self.assertRaises(ValueError):
            await gather_limited([], limit=0)

    async def test_map_unordered_yields_as_tasks_complete(self) -> None:
        first_yielded = asyncio.Event()

        async def work(item_id: int) -> int:
            if item_id == 0:
                await first_yielded.wait()
                return 0
            return 1

        results: list[int] = []
        async for res in map_unordered(work, [0, 1], limit=2):
            results.append(res)
            if res == 1:
                first_yielded.set()

        self.assertEqual(results, [1, 0])

    async def test_map_unordered_bounds_concurrency(self) -> None:
        active = 0
        peak = 0

        async def work(value: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.005)
            active -= 1
            return value

        results: list[int] = []
        async for res in map_unordered(work, range(6), limit=2):
            results.append(res)

        self.assertEqual(set(results), set(range(6)))
        self.assertLessEqual(peak, 2)

    async def test_map_unordered_invalid_limit(self) -> None:
        async def dummy(x: int) -> int:
            return x

        with self.assertRaises(ValueError):
            async for _ in map_unordered(dummy, [1], limit=0):
                pass

        with self.assertRaises(ValueError):
            async for _ in map_unordered(dummy, [1], limit=-1):  # type: ignore[arg-type]
                pass

    async def test_map_unordered_exception_cancels_pending(self) -> None:
        cancelled = False

        async def slow_work() -> int:
            nonlocal cancelled
            try:
                await asyncio.sleep(5.0)
                return 1
            except asyncio.CancelledError:
                cancelled = True
                raise

        async def fail_work() -> int:
            await asyncio.sleep(0.005)
            raise RuntimeError("boom")

        async def dispatcher(kind: str) -> int:
            if kind == "slow":
                return await slow_work()
            return await fail_work()

        with self.assertRaises(RuntimeError):
            async for _ in map_unordered(dispatcher, ["slow", "fail"], limit=2):
                pass

        self.assertTrue(cancelled)

    async def test_map_unordered_sibling_exceptions_observed_without_warning(
        self,
    ) -> None:
        loop = asyncio.get_running_loop()
        old_handler = loop.get_exception_handler()
        captured_contexts: list[dict[str, Any]] = []

        def custom_handler(
            _loop: asyncio.AbstractEventLoop, context: dict[str, Any]
        ) -> None:
            captured_contexts.append(context)

        loop.set_exception_handler(custom_handler)
        barrier = asyncio.Event()

        async def fail_together(val: int) -> int:
            await barrier.wait()
            raise RuntimeError(f"error_{val}")

        gen = map_unordered(fail_together, [1, 2], limit=2)
        iter_task = asyncio.create_task(gen.__anext__())
        await asyncio.sleep(0)
        barrier.set()

        try:
            with self.assertRaises(RuntimeError):
                await iter_task
        finally:
            await gen.aclose()
            gc.collect()
            await asyncio.sleep(0)
            loop.set_exception_handler(old_handler)

        unretrieved = [
            ctx
            for ctx in captured_contexts
            if "was never retrieved" in str(ctx.get("message", ""))
        ]
        self.assertEqual(unretrieved, [])

    async def test_map_unordered_early_break_cancels_active(self) -> None:
        cancelled = False

        async def slow_work(val: int) -> int:
            nonlocal cancelled
            if val == 1:
                return 1
            try:
                await asyncio.sleep(5.0)
                return 2
            except asyncio.CancelledError:
                cancelled = True
                raise

        async for res in map_unordered(slow_work, [1, 2], limit=2):
            if res == 1:
                break

        await asyncio.sleep(0.01)
        self.assertTrue(cancelled)
