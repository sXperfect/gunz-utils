"""Tests for Wave 1 additions: Cache & Workflow DAG (#1 - #14)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import unittest

from gunz_utils.cache import (
    CacheInfo,
    RecencyTTLPolicy,
    SingleFlight,
    async_ttl_cache,
    ttl_cache,
)
from gunz_utils.dag import WorkflowDAG, WorkflowStage


class TestWave1Cache(unittest.IsolatedAsyncioTestCase):
    def test_item1_cache_info_hit_rate(self) -> None:
        info_empty = CacheInfo(hits=0, misses=0, size=0, maxsize=10)
        self.assertEqual(info_empty.hit_rate, 0.0)

        info_some = CacheInfo(hits=3, misses=1, size=4, maxsize=10)
        self.assertEqual(info_some.hit_rate, 0.75)

    def test_item2_eager_callable_validation(self) -> None:
        decorator = ttl_cache(ttl=10.0)
        with self.assertRaises(TypeError):
            decorator("not_callable")  # type: ignore[arg-type]

        async_decorator = async_ttl_cache(ttl=10.0)
        with self.assertRaises(TypeError):
            async_decorator(12345)  # type: ignore[arg-type]

    def test_item3_injectable_clock_sync(self) -> None:
        current_time = 100.0

        def fake_clock() -> float:
            return current_time

        with self.assertRaises(TypeError):
            ttl_cache(ttl=10.0, clock="invalid")  # type: ignore[arg-type]

        calls = 0

        @ttl_cache(ttl=10.0, clock=fake_clock)
        def compute(x: int) -> int:
            nonlocal calls
            calls += 1
            return x * 2

        self.assertEqual(compute(5), 10)
        self.assertEqual(calls, 1)

        # Hit within TTL
        current_time = 105.0
        self.assertEqual(compute(5), 10)
        self.assertEqual(calls, 1)

        # Expired after TTL
        current_time = 111.0
        self.assertEqual(compute(5), 10)
        self.assertEqual(calls, 2)

    async def test_item3_injectable_clock_async(self) -> None:
        current_time = 200.0

        def fake_clock() -> float:
            return current_time

        with self.assertRaises(TypeError):
            async_ttl_cache(ttl=10.0, clock=123)  # type: ignore[arg-type]

        calls = 0

        @async_ttl_cache(ttl=10.0, clock=fake_clock)
        async def fetch(x: int) -> int:
            nonlocal calls
            calls += 1
            return x + 100

        self.assertEqual(await fetch(1), 101)
        self.assertEqual(calls, 1)

        current_time = 205.0
        self.assertEqual(await fetch(1), 101)
        self.assertEqual(calls, 1)

        current_time = 215.0
        self.assertEqual(await fetch(1), 101)
        self.assertEqual(calls, 2)

    def test_item4_cache_invalidate_sync(self) -> None:
        calls = 0

        @ttl_cache(ttl=60.0)
        def get_val(a: int, b: str = "x") -> str:
            nonlocal calls
            calls += 1
            return f"{a}:{b}"

        self.assertEqual(get_val(1, b="y"), "1:y")
        self.assertEqual(calls, 1)

        # Invalidate non-existent key returns False
        self.assertFalse(get_val.cache_invalidate(2, b="y"))

        # Invalidate existing key returns True
        self.assertTrue(get_val.cache_invalidate(1, b="y"))
        self.assertFalse(get_val.cache_invalidate(1, b="y"))

        # Next call computes afresh
        self.assertEqual(get_val(1, b="y"), "1:y")
        self.assertEqual(calls, 2)

    async def test_item4_cache_invalidate_async(self) -> None:
        calls = 0

        @async_ttl_cache(ttl=60.0)
        async def get_val_async(k: int) -> int:
            nonlocal calls
            calls += 1
            return k * 10

        self.assertEqual(await get_val_async(3), 30)
        self.assertEqual(calls, 1)

        self.assertFalse(await get_val_async.cache_invalidate(99))
        self.assertTrue(await get_val_async.cache_invalidate(3))
        self.assertFalse(await get_val_async.cache_invalidate(3))

        self.assertEqual(await get_val_async(3), 30)
        self.assertEqual(calls, 2)

    async def test_item5_single_flight_introspection(self) -> None:
        sf = SingleFlight()
        self.assertEqual(sf.in_flight_count, 0)
        self.assertFalse(sf.is_in_flight("k1"))

        with self.assertRaises(TypeError):
            sf.is_in_flight([1, 2])  # type: ignore[arg-type]

        release_event = asyncio.Event()

        async def worker() -> str:
            self.assertEqual(sf.in_flight_count, 1)
            self.assertTrue(sf.is_in_flight("k1"))
            await release_event.wait()
            return "done"

        task = asyncio.create_task(sf.run("k1", worker))
        await asyncio.sleep(0.01)

        self.assertEqual(sf.in_flight_count, 1)
        self.assertTrue(sf.is_in_flight("k1"))
        self.assertFalse(sf.is_in_flight("k2"))

        release_event.set()
        res = await task
        self.assertEqual(res, "done")
        self.assertEqual(sf.in_flight_count, 0)
        self.assertFalse(sf.is_in_flight("k1"))

    def test_item6_and_7_recency_ttl_policy(self) -> None:
        policy = RecencyTTLPolicy(
            recent_window=timedelta(minutes=30),
            recent_ttl=timedelta(minutes=5),
            historical_ttl=timedelta(hours=2),
            empty_recent_ttl=timedelta(seconds=30),
        )

        now = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
        recent_time = now - timedelta(minutes=10)
        old_time = now - timedelta(hours=5)

        # Item 6: strict empty bool validation
        with self.assertRaises(TypeError):
            policy.ttl_for(recent_time, empty="invalid", now=now)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            policy.ttl_seconds_for(recent_time, empty=1, now=now)  # type: ignore[arg-type]

        # Item 7: ttl_seconds_for
        sec_recent = policy.ttl_seconds_for(recent_time, empty=False, now=now)
        self.assertEqual(sec_recent, 300.0)

        sec_empty = policy.ttl_seconds_for(recent_time, empty=True, now=now)
        self.assertEqual(sec_empty, 30.0)

        sec_old = policy.ttl_seconds_for(old_time, empty=False, now=now)
        self.assertEqual(sec_old, 7200.0)


class TestWave1DAG(unittest.IsolatedAsyncioTestCase):
    def test_item8_bare_string_dependencies_rejection(self) -> None:
        with self.assertRaises(TypeError):
            WorkflowStage(name="s1", run=lambda _: 1, dependencies="stage_a")  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            WorkflowStage(name="s2", run=lambda _: 1, dependencies=b"stage_b")  # type: ignore[arg-type]

    def test_item9_whitespace_stage_name_rejection(self) -> None:
        with self.assertRaises(ValueError):
            WorkflowStage(name="   ", run=lambda _: 1)

        with self.assertRaises(ValueError):
            WorkflowStage(name="s1", run=lambda _: 1, dependencies=("  ",))

    def test_item10_workflow_dag_stage_element_type_validation(self) -> None:
        with self.assertRaises(TypeError):
            WorkflowDAG(["not_a_stage"])  # type: ignore[list-item]

    def test_item11_fingerprint_memoization(self) -> None:
        s1 = WorkflowStage(name="a", run=lambda _: 1, fingerprint="fp_a")
        s2 = WorkflowStage(name="b", run=lambda d: d["a"] + 1, dependencies=("a",), fingerprint="fp_b")
        dag = WorkflowDAG([s1, s2])

        fp1 = dag.effective_fingerprint("b")
        self.assertIsNotNone(fp1)
        self.assertIn("b", dag._fingerprint_memo)
        self.assertEqual(dag._fingerprint_memo["b"], fp1)

        # Repeated call returns identical memoized result
        self.assertEqual(dag.effective_fingerprint("b"), fp1)

    def test_item12_parallel_layers(self) -> None:
        # A, B (independent, layer 0) -> C (depends on A), D (depends on A, B) (layer 1) -> E (depends on C, D) (layer 2)
        s_a = WorkflowStage(name="a", run=lambda _: 1)
        s_b = WorkflowStage(name="b", run=lambda _: 2)
        s_c = WorkflowStage(name="c", run=lambda d: d["a"] + 1, dependencies=("a",))
        s_d = WorkflowStage(name="d", run=lambda d: d["a"] + d["b"], dependencies=("a", "b"))
        s_e = WorkflowStage(name="e", run=lambda d: d["c"] + d["d"], dependencies=("c", "d"))

        dag = WorkflowDAG([s_a, s_b, s_c, s_d, s_e])
        layers = dag.parallel_layers()
        self.assertEqual(layers, (("a", "b"), ("c", "d"), ("e",)))

    def test_item13_dependencies_and_dependents_of(self) -> None:
        s_a = WorkflowStage(name="a", run=lambda _: 1)
        s_b = WorkflowStage(name="b", run=lambda d: d["a"], dependencies=("a",))
        s_c = WorkflowStage(name="c", run=lambda d: d["b"], dependencies=("b",))
        s_d = WorkflowStage(name="d", run=lambda d: d["a"], dependencies=("a",))

        dag = WorkflowDAG([s_a, s_b, s_c, s_d])

        # dependencies_of
        self.assertEqual(dag.dependencies_of("c", transitive=False), ("b",))
        self.assertEqual(dag.dependencies_of("c", transitive=True), ("a", "b"))
        self.assertEqual(dag.dependencies_of("a", transitive=True), ())

        # dependents_of
        self.assertEqual(set(dag.dependents_of("a", transitive=False)), {"b", "d"})
        self.assertEqual(set(dag.dependents_of("a", transitive=True)), {"b", "c", "d"})
        self.assertEqual(dag.dependents_of("c", transitive=True), ())

        with self.assertRaises(KeyError):
            dag.dependencies_of("nonexistent")
        with self.assertRaises(TypeError):
            dag.dependencies_of("a", transitive="yes")  # type: ignore[arg-type]
        with self.assertRaises(KeyError):
            dag.dependents_of("nonexistent")
        with self.assertRaises(TypeError):
            dag.dependents_of("a", transitive=1)  # type: ignore[arg-type]

    async def test_item14_cache_type_validation(self) -> None:
        s1 = WorkflowStage(name="a", run=lambda _: 1, fingerprint="fp1")
        dag = WorkflowDAG([s1])

        with self.assertRaises(TypeError):
            dag.execute(cache=[("a", "fp1")])  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            await dag.async_execute(cache="invalid_cache")  # type: ignore[arg-type]

        valid_cache: dict[tuple[str, str], int] = {}
        out = dag.execute(cache=valid_cache)
        self.assertEqual(out["a"], 1)
        self.assertEqual(len(valid_cache), 1)

        async_out = await dag.async_execute(cache=valid_cache)
        self.assertEqual(async_out["a"], 1)


if __name__ == "__main__":
    unittest.main()
