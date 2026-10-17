# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
import threading
import unittest
import weakref
from datetime import UTC, datetime, timedelta

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.cache import (
    RecencyTTLPolicy,
    SingleFlight,
    async_ttl_cache,
    ttl_cache,
)


class TestTTLCache(unittest.TestCase):
    def test_rejects_invalid_ttl_and_capacity_domains(self) -> None:
        for value in (math.nan, math.inf, -math.inf, True):
            with self.subTest(ttl=value):
                with self.assertRaises(ValueError):
                    ttl_cache(ttl=value)
        for value in (0, -1, True):
            with self.subTest(maxsize=value):
                with self.assertRaises(ValueError):
                    ttl_cache(ttl=1, maxsize=value)

    def test_cache_hit(self) -> None:
        calls = 0

        @ttl_cache(ttl=60)
        def work(
            value: int,
        ) -> int:
            nonlocal calls
            calls += 1
            return value * 2

        self.assertEqual(work(2), 4)
        self.assertEqual(work(2), 4)
        self.assertEqual(calls, 1)


    def test_unhashable_arguments_bypass_cache(self) -> None:
        calls = 0

        @ttl_cache(ttl=60)
        def work(
            value: list[int],
        ) -> int:
            nonlocal calls
            calls += 1
            return len(value)

        self.assertEqual(work([1]), 1)
        self.assertEqual(work([1]), 1)
        self.assertEqual(calls, 2)

    def test_lru_capacity_eviction(self) -> None:
        calls = 0

        @ttl_cache(ttl=60, maxsize=2)
        def work(
            x: int,
        ) -> int:
            nonlocal calls
            calls += 1
            return x * 10

        self.assertEqual(work(1), 10)
        self.assertEqual(work(2), 20)
        self.assertEqual(calls, 2)
        self.assertEqual(work.cache_info().size, 2)

        #? Access 1 to make it most recently used
        self.assertEqual(work(1), 10)
        self.assertEqual(calls, 2)

        #? Add 3, which must evict 2 (least recently used)
        self.assertEqual(work(3), 30)
        self.assertEqual(calls, 3)
        self.assertEqual(work.cache_info().size, 2)

        #? 2 was evicted, so it must trigger a re-computation
        self.assertEqual(work(2), 20)
        self.assertEqual(calls, 4)

    def test_ttl_expiry(self) -> None:
        calls = 0

        @ttl_cache(ttl=0.01, maxsize=10)
        def work(
            x: int,
        ) -> int:
            nonlocal calls
            calls += 1
            return x + 1

        self.assertEqual(work(1), 2)
        self.assertEqual(calls, 1)
        self.assertEqual(work(1), 2)
        self.assertEqual(calls, 1)

        import time

        time.sleep(0.015)

        self.assertEqual(work(1), 2)
        self.assertEqual(calls, 2)


    def test_cache_clear_does_not_reinsert_inflight_sync_result(self) -> None:
        started = threading.Event()
        release = threading.Event()
        calls = 0
        results: list[int] = []
        failures: list[BaseException] = []

        @ttl_cache(ttl=60)
        def work(
            value: int,
        ) -> int:
            nonlocal calls
            calls += 1
            version = calls
            if version == 1:
                started.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("test producer was not released")
            return version

        def old_caller() -> None:
            try:
                results.append(work(1))
            except BaseException as exc:
                failures.append(exc)

        thread = threading.Thread(target=old_caller)
        thread.start()
        try:
            self.assertTrue(started.wait(timeout=5))
            work.cache_clear()
            self.assertEqual(work.cache_info().size, 0)
            self.assertEqual(work(1), 2)
        finally:
            release.set()
            thread.join(timeout=5)

        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results, [1])
        self.assertEqual(work(1), 2)
        self.assertEqual(calls, 2)


class TestSingleFlight(unittest.IsolatedAsyncioTestCase):
    async def test_coalesces_same_key(self) -> None:
        flight = SingleFlight()
        calls = 0

        async def work() -> int:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return 7

        results = await asyncio.gather(
            flight.run("same", work),
            flight.run("same", work),
            flight.run("same", work),
        )
        self.assertEqual(results, [7, 7, 7])
        self.assertEqual(calls, 1)

    async def test_unhashable_key_rejected(self) -> None:
        flight = SingleFlight()

        async def work() -> int:
            return 1

        with self.assertRaises(TypeError):
            await flight.run([1, 2], work)  # type: ignore[arg-type]

    async def test_non_callable_factory_rejected(self) -> None:
        flight = SingleFlight()

        with self.assertRaises(TypeError):
            await flight.run("key", None)  # type: ignore[arg-type]

    async def test_partial_waiter_cancellation_does_not_abort_peer(self) -> None:
        flight = SingleFlight()
        started = asyncio.Event()

        async def slow_work() -> str:
            started.set()
            await asyncio.sleep(0.02)
            return "ok"

        task1 = asyncio.create_task(flight.run("k", slow_work))
        task2 = asyncio.create_task(flight.run("k", slow_work))
        await started.wait()
        task1.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task1
        self.assertEqual(await task2, "ok")




class TestRecencyTTLPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = RecencyTTLPolicy(
            recent_window=timedelta(days=5),
            recent_ttl=timedelta(hours=6),
            historical_ttl=timedelta(days=30),
            empty_recent_ttl=timedelta(hours=1),
        )
        self.now = datetime(
            2026,
            9,
            27,
            12,
            0,
            tzinfo=UTC,
        )

    def test_selects_recent_and_historical_ttls(self) -> None:
        self.assertEqual(
            self.policy.ttl_for(
                self.now - timedelta(days=2),
                now=self.now,
            ),
            timedelta(hours=6),
        )
        self.assertEqual(
            self.policy.ttl_for(
                self.now - timedelta(days=10),
                now=self.now,
            ),
            timedelta(days=30),
        )

    def test_recent_empty_result_uses_empty_ttl(self) -> None:
        self.assertEqual(
            self.policy.ttl_for(
                self.now - timedelta(hours=2),
                empty=True,
                now=self.now,
            ),
            timedelta(hours=1),
        )

    def test_future_timestamp_is_treated_as_recent(self) -> None:
        self.assertEqual(
            self.policy.ttl_for(
                self.now + timedelta(hours=1),
                now=self.now,
            ),
            timedelta(hours=6),
        )

    def test_requires_timezone_aware_datetimes(self) -> None:
        naive = datetime(2026, 9, 27, 12, 0)

        with self.assertRaises(ValueError):
            self.policy.ttl_for(
                naive,
                now=self.now,
            )
        with self.assertRaises(ValueError):
            self.policy.ttl_for(
                self.now,
                now=naive,
            )

    def test_rejects_negative_durations(self) -> None:
        with self.assertRaises(ValueError):
            RecencyTTLPolicy(
                recent_window=timedelta(days=-1),
                recent_ttl=timedelta(hours=1),
                historical_ttl=timedelta(days=1),
            )


class TestAsyncTTLCache(unittest.IsolatedAsyncioTestCase):
    async def test_all_callers_cancel_releases_in_flight_and_payload(self) -> None:
        class Payload:
            def __init__(self,
                size: int,
            ) -> None:
                self.data = bytearray(size)

        @async_ttl_cache(ttl=60.0, maxsize=1)
        async def compute(
            key: str,
            payload: Payload,
        ) -> Payload:
            await asyncio.sleep(0.05)
            return payload

        weak_refs = []
        for i in range(10):
            data = Payload(1024)
            weak_refs.append(weakref.ref(data))
            task = asyncio.create_task(compute(f"k{i}", data))
            await asyncio.sleep(0.001)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        #? Wait for all background producer tasks to finish
        await asyncio.sleep(0.1)

        #? In-flight dictionary should be completely empty
        self.assertEqual(len(compute._in_flight), 0)
        #? Because maxsize=1, at most 1 payload is retained in cache
        alive = sum(1 for r in weak_refs if r() is not None)
        self.assertLessEqual(alive, 1)

        #? cache_clear should drop the remaining entry
        await compute.cache_clear()
        self.assertEqual(len(compute._cache), 0)
        self.assertEqual(len(compute._in_flight), 0)

    async def test_single_flight_all_callers_cancel_task_cleanup(self) -> None:
        flight = SingleFlight()

        async def work() -> str:
            await asyncio.sleep(0.05)
            return "done"

        task = asyncio.create_task(flight.run("key", work))
        await asyncio.sleep(0.001)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        await asyncio.sleep(0.1)
        self.assertEqual(len(flight._tasks), 0)

    async def test_async_ttl_cache_coalesced_concurrent_misses(self) -> None:
        calls = 0

        @async_ttl_cache(ttl=60.0, maxsize=10)
        async def work(
            x: int,
        ) -> int:
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.02)
            return x * 100

        results = await asyncio.gather(*(work(5) for _ in range(5)))
        self.assertEqual(results, [500, 500, 500, 500, 500])
        self.assertEqual(calls, 1)

    async def test_async_ttl_cache_unhashable_arguments(self) -> None:
        calls = 0

        @async_ttl_cache(ttl=60.0, maxsize=10)
        async def work(
            items: list[int],
        ) -> int:
            nonlocal calls
            calls += 1
            return len(items)

        self.assertEqual(await work([1, 2]), 2)
        self.assertEqual(await work([1, 2]), 2)
        self.assertEqual(calls, 2)


class TestCacheMethodBinding(unittest.IsolatedAsyncioTestCase):
    def test_sync_ttl_cache_method_binding(self) -> None:
        class Service:
            def __init__(self,
                multiplier: int,
            ) -> None:
                self.multiplier = multiplier

            @ttl_cache(ttl=60)
            def compute(self,
                x: int,
            ) -> int:
                return self.multiplier * x

            @classmethod
            @ttl_cache(ttl=60)
            def class_method_first(cls,
                x: int,
            ) -> str:
                return f"{cls.__name__}:{x}"

            @ttl_cache(ttl=60)
            @classmethod
            def cache_first_class(cls,
                x: int,
            ) -> str:
                return f"{cls.__name__}:{x}"

            @staticmethod
            @ttl_cache(ttl=60)
            def static_method_first(
                x: int,
            ) -> int:
                return x * 10

            @ttl_cache(ttl=60)
            @staticmethod
            def cache_first_static(
                x: int,
            ) -> int:
                return x * 20

        s1 = Service(2)
        s2 = Service(3)

        self.assertEqual(s1.compute(5), 10)
        self.assertEqual(s2.compute(5), 15)

        self.assertEqual(s1.class_method_first(4), "Service:4")
        self.assertEqual(Service.class_method_first(4), "Service:4")

        self.assertEqual(s1.cache_first_class(4), "Service:4")
        self.assertEqual(Service.cache_first_class(4), "Service:4")

        self.assertEqual(s1.static_method_first(3), 30)
        self.assertEqual(Service.static_method_first(3), 30)

        self.assertEqual(s1.cache_first_static(3), 60)
        self.assertEqual(Service.cache_first_static(3), 60)

        #? Test cache_clear and cache_info on bound methods
        info = s1.compute.cache_info()
        self.assertEqual(info.hits, 0)
        s1.compute(5)
        self.assertEqual(s1.compute.cache_info().hits, 1)
        s1.compute.cache_clear()
        self.assertEqual(s1.compute.cache_info().hits, 0)

    async def test_async_ttl_cache_method_binding(self) -> None:
        class AsyncService:
            def __init__(self,
                multiplier: int,
            ) -> None:
                self.multiplier = multiplier

            @async_ttl_cache(ttl=60)
            async def compute(self,
                x: int,
            ) -> int:
                return self.multiplier * x

            @classmethod
            @async_ttl_cache(ttl=60)
            async def class_method_first(cls,
                x: int,
            ) -> str:
                return f"{cls.__name__}:{x}"

            @async_ttl_cache(ttl=60)
            @classmethod
            async def cache_first_class(cls,
                x: int,
            ) -> str:
                return f"{cls.__name__}:{x}"

            @staticmethod
            @async_ttl_cache(ttl=60)
            async def static_method_first(
                x: int,
            ) -> int:
                return x * 10

            @async_ttl_cache(ttl=60)
            @staticmethod
            async def cache_first_static(
                x: int,
            ) -> int:
                return x * 20

        s = AsyncService(5)
        self.assertEqual(await s.compute(3), 15)
        self.assertEqual(await s.class_method_first(2), "AsyncService:2")
        self.assertEqual(await AsyncService.class_method_first(2), "AsyncService:2")
        self.assertEqual(await s.cache_first_class(2), "AsyncService:2")
        self.assertEqual(await AsyncService.cache_first_class(2), "AsyncService:2")
        self.assertEqual(await s.static_method_first(4), 40)
        self.assertEqual(await AsyncService.static_method_first(4), 40)
        self.assertEqual(await s.cache_first_static(4), 80)
        self.assertEqual(await AsyncService.cache_first_static(4), 80)

        await s.compute.cache_clear()
