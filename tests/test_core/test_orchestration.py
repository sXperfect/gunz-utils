"""Tests for autonomous agent loop and distributed worker execution primitives."""

from __future__ import annotations

import asyncio
import math
import time
import unittest

from gunz_utils.dag import WorkflowDAG, WorkflowExecutionError, WorkflowStage
from gunz_utils.limits import BudgetExceededError, Limits, ResourceBudget
from gunz_utils.signals import GracefulShutdown


class TestResourceBudgetSteps(unittest.TestCase):
    def test_limits_check_steps(self) -> None:
        limits = Limits(max_steps=5)
        limits.check_steps(3)
        limits.check_steps(5)
        with self.assertRaises(ValueError):
            limits.check_steps(6)
        with self.assertRaises(ValueError):
            limits.check_steps(-1)

    def test_budget_step_consumption(self) -> None:
        budget = ResourceBudget(max_steps=3)
        self.assertEqual(budget.remaining_steps, 3)
        self.assertEqual(budget.steps_used, 0)

        self.assertEqual(budget.consume_steps(1), 1)
        self.assertEqual(budget.remaining_steps, 2)

        self.assertEqual(budget.consume_steps(2), 3)
        self.assertEqual(budget.remaining_steps, 0)

        with self.assertRaises(BudgetExceededError):
            budget.consume_steps(1)

    def test_budget_step_context_manager(self) -> None:
        budget = ResourceBudget(max_steps=2)
        with budget.step():
            pass
        self.assertEqual(budget.steps_used, 1)

        with budget.step():
            pass
        self.assertEqual(budget.steps_used, 2)

        with self.assertRaises(BudgetExceededError):
            with budget.step():
                pass


class TestWorkflowDAGAsyncAndCompensation(unittest.IsolatedAsyncioTestCase):
    async def test_async_execute_concurrent_branches(self) -> None:
        timeline: list[tuple[str, float]] = []
        t0 = time.monotonic()

        async def stage_a(_deps: dict[str, object]) -> str:
            await asyncio.sleep(0.05)
            timeline.append(("a", time.monotonic() - t0))
            return "res_a"

        async def stage_b(_deps: dict[str, object]) -> str:
            await asyncio.sleep(0.05)
            timeline.append(("b", time.monotonic() - t0))
            return "res_b"

        async def stage_c(deps: dict[str, object]) -> str:
            timeline.append(("c", time.monotonic() - t0))
            return f"{deps['a']}+{deps['b']}"

        dag = WorkflowDAG(
            [
                WorkflowStage("a", stage_a),
                WorkflowStage("b", stage_b),
                WorkflowStage("c", stage_c, dependencies=("a", "b")),
            ]
        )

        outputs = await dag.async_execute()
        self.assertEqual(outputs["c"], "res_a+res_b")
        total_time = time.monotonic() - t0
        # A and B run concurrently, so total time should be close to 0.05s, not 0.10s
        self.assertLess(total_time, 0.12)
        stage_names = [name for name, _ in timeline]
        self.assertEqual(stage_names[-1], "c")
        self.assertEqual(set(stage_names[:2]), {"a", "b"})

    async def test_async_execute_concurrency_limit(self) -> None:
        running = 0
        peak_running = 0

        async def worker(_deps: dict[str, object]) -> int:
            nonlocal running, peak_running
            running += 1
            peak_running = max(peak_running, running)
            await asyncio.sleep(0.02)
            running -= 1
            return 1

        dag = WorkflowDAG([WorkflowStage(f"s{i}", worker) for i in range(5)])
        outputs = await dag.async_execute(concurrency_limit=2)
        self.assertEqual(len(outputs), 5)
        self.assertLessEqual(peak_running, 2)

    async def test_async_execute_with_budget(self) -> None:
        budget = ResourceBudget(max_steps=2)

        async def noop(_deps: dict[str, object]) -> int:
            return 1

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", noop),
                WorkflowStage("s2", noop, dependencies=("s1",)),
                WorkflowStage("s3", noop, dependencies=("s2",)),
            ]
        )

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute(budget=budget)
        self.assertEqual(cm.exception.stage_name, "s3")
        self.assertIsInstance(cm.exception.cause, BudgetExceededError)

    async def test_async_rollback_on_failure(self) -> None:
        compensated: list[str] = []

        async def stage_1(_deps: dict[str, object]) -> str:
            return "data_1"

        def comp_1(out: object) -> None:
            compensated.append(f"comp_1:{out}")

        async def stage_2(_deps: dict[str, object]) -> str:
            return "data_2"

        async def comp_2(out: object) -> None:
            compensated.append(f"comp_2:{out}")

        async def stage_3(_deps: dict[str, object]) -> str:
            raise RuntimeError("stage 3 blew up")

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",), compensate=comp_2),
                WorkflowStage("s3", stage_3, dependencies=("s2",)),
            ]
        )

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute()

        self.assertEqual(cm.exception.stage_name, "s3")
        # Compensation should occur in reverse completion order: s2 then s1
        self.assertEqual(compensated, ["comp_2:data_2", "comp_1:data_1"])

    async def test_async_execute_cancels_running_siblings_on_failure(self) -> None:
        cancelled = False
        started = asyncio.Event()

        async def slow_stage(_deps: dict[str, object]) -> str:
            nonlocal cancelled
            started.set()
            try:
                await asyncio.sleep(10.0)
                return "slow_done"
            except asyncio.CancelledError:
                cancelled = True
                raise

        async def fail_stage(_deps: dict[str, object]) -> str:
            await started.wait()
            raise RuntimeError("fail_stage blew up")

        dag = WorkflowDAG(
            [
                WorkflowStage("slow", slow_stage),
                WorkflowStage("fail", fail_stage),
            ]
        )

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute()

        self.assertEqual(cm.exception.stage_name, "fail")
        self.assertTrue(cancelled)

    def test_sync_rollback_on_failure(self) -> None:
        compensated: list[str] = []

        def s1(_deps: dict[str, object]) -> int:
            return 10

        def comp_1(out: object) -> None:
            compensated.append(f"comp_1:{out}")

        def s2(_deps: dict[str, object]) -> int:
            raise ValueError("s2 fail")

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", s1, compensate=comp_1),
                WorkflowStage("s2", s2, dependencies=("s1",)),
            ]
        )

        with self.assertRaises(WorkflowExecutionError) as cm:
            dag.execute()

        self.assertEqual(cm.exception.stage_name, "s2")
        self.assertEqual(compensated, ["comp_1:10"])

    async def test_async_execute_stage_cancellation_triggers_compensation(self) -> None:
        compensated: list[str] = []

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        def comp_1(out: object) -> None:
            compensated.append(f"comp_1:{out}")

        async def stage_2(_deps: dict[str, object]) -> str:
            raise asyncio.CancelledError()

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ]
        )

        with self.assertRaises(asyncio.CancelledError):
            await dag.async_execute()

        self.assertEqual(compensated, ["comp_1:res_1"])

    async def test_async_execute_caller_cancel_triggers_compensation(
        self,
    ) -> None:
        compensated: list[str] = []
        stage1_done = asyncio.Event()

        async def stage_1(_deps: dict[str, object]) -> str:
            stage1_done.set()
            return "res_1"

        def comp_1(out: object) -> None:
            compensated.append(f"comp_1:{out}")

        async def stage_2(_deps: dict[str, object]) -> str:
            await asyncio.sleep(5.0)
            return "res_2"

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ]
        )

        task = asyncio.create_task(dag.async_execute())
        await stage1_done.wait()
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertEqual(compensated, ["comp_1:res_1"])

    def test_cache_entries_not_published_on_sync_failure_and_clean_retry(self) -> None:
        cache: dict[tuple[str, str], object] = {}
        created: list[str] = []
        compensated: list[str] = []
        fail_stage_2 = True

        def stage_1(_deps: dict[str, object]) -> str:
            created.append("res_1")
            return "res_1"

        def comp_1(out: object) -> None:
            compensated.append(str(out))

        def stage_2(_deps: dict[str, object]) -> str:
            if fail_stage_2:
                raise RuntimeError("stage 2 error")
            return "res_2"

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ]
        )

        with self.assertRaises(WorkflowExecutionError):
            dag.execute(cache=cache)

        self.assertEqual(created, ["res_1"])
        self.assertEqual(compensated, ["res_1"])
        self.assertEqual(cache, {}, "Compensated outputs must not remain cached")

        # Retry after fix
        fail_stage_2 = False
        outputs = dag.execute(cache=cache)
        self.assertEqual(outputs, {"s1": "res_1", "s2": "res_2"})
        self.assertEqual(
            created, ["res_1", "res_1"], "Stage 1 must re-execute on retry"
        )
        fp = dag.effective_fingerprint("s1")
        self.assertIn(("s1", fp), cache, "Successful run commits cache")

    async def test_cache_entries_not_published_on_async_failure_retry(
        self,
    ) -> None:
        cache: dict[tuple[str, str], object] = {}
        created: list[str] = []
        compensated: list[str] = []
        fail_stage_2 = True

        async def stage_1(_deps: dict[str, object]) -> str:
            created.append("res_1")
            return "res_1"

        async def comp_1(out: object) -> None:
            compensated.append(str(out))

        async def stage_2(_deps: dict[str, object]) -> str:
            if fail_stage_2:
                raise RuntimeError("async stage 2 error")
            return "res_2"

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ]
        )

        with self.assertRaises(WorkflowExecutionError):
            await dag.async_execute(cache=cache)

        self.assertEqual(created, ["res_1"])
        self.assertEqual(compensated, ["res_1"])
        self.assertEqual(cache, {}, "Compensated outputs must not remain cached")

        # Retry after fix
        fail_stage_2 = False
        outputs = await dag.async_execute(cache=cache)
        self.assertEqual(outputs, {"s1": "res_1", "s2": "res_2"})
        self.assertEqual(
            created, ["res_1", "res_1"], "Stage 1 must re-execute on retry"
        )
        fp = dag.effective_fingerprint("s1")
        self.assertIn(("s1", fp), cache, "Successful run commits cache")

    async def test_cache_hits_are_not_compensated_on_downstream_failure(self) -> None:
        compensated: list[str] = []

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        def comp_1(out: object) -> None:
            compensated.append(str(out))

        async def stage_2(_deps: dict[str, object]) -> str:
            raise RuntimeError("downstream failure")

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ]
        )
        fp = dag.effective_fingerprint("s1")
        assert fp is not None
        cache: dict[tuple[str, str], object] = {("s1", fp): "cached_res_1"}

        with self.assertRaises(WorkflowExecutionError):
            await dag.async_execute(cache=cache)

        self.assertEqual(compensated, [], "Cache hits must not be compensated")

    async def test_async_execute_eager_factory_sibling_cancellation(self) -> None:
        loop = asyncio.get_running_loop()
        eager_factory = getattr(asyncio, "eager_task_factory", None)
        old_factory = loop.get_task_factory()
        if eager_factory is not None:
            loop.set_task_factory(eager_factory)
        try:
            sibling_cancelled = False

            async def stage_1(_deps: dict[str, object]) -> str:
                nonlocal sibling_cancelled
                try:
                    await asyncio.sleep(10.0)
                    return "res_1"
                except asyncio.CancelledError:
                    sibling_cancelled = True
                    raise

            async def stage_2(_deps: dict[str, object]) -> str:
                raise RuntimeError("immediate failure")

            dag = WorkflowDAG(
                [
                    WorkflowStage("s1", stage_1),
                    WorkflowStage("s2", stage_2),
                ]
            )

            with self.assertRaises(WorkflowExecutionError):
                await dag.async_execute()

            self.assertTrue(sibling_cancelled)
        finally:
            loop.set_task_factory(old_factory)

    async def test_async_execute_repeated_cancellation_waits_for_compensation(
        self,
    ) -> None:
        comp_done = False
        comp_started = asyncio.Event()
        release_comp = asyncio.Event()

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        async def comp_1(_out: object) -> None:
            nonlocal comp_done
            comp_started.set()
            await release_comp.wait()
            comp_done = True

        async def stage_2(_deps: dict[str, object]) -> str:
            raise asyncio.CancelledError()

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ]
        )

        task = asyncio.create_task(dag.async_execute())
        await comp_started.wait()

        # Cancellation while compensation is running in background
        task.cancel()
        await asyncio.sleep(0.01)
        self.assertFalse(
            task.done(), "Task must not return before compensation finishes"
        )
        self.assertFalse(comp_done)

        # Release compensation
        release_comp.set()
        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(
            comp_done, "Compensation must be completed when task returns"
        )

    def test_cache_publication_failure_sync(self) -> None:
        compensated: list[str] = []

        class FailingCache(dict[tuple[str, str], object]):
            def __setitem__(self, key: tuple[str, str], val: object) -> None:
                if key[0] == "s2":
                    raise OSError("disk full")
                super().__setitem__(key, val)

        def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        def comp_1(out: object) -> None:
            compensated.append(str(out))

        def stage_2(_deps: dict[str, object]) -> str:
            return "res_2"

        def comp_2(out: object) -> None:
            compensated.append(str(out))

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage(
                    "s2",
                    stage_2,
                    fingerprint="f2",
                    dependencies=("s1",),
                    compensate=comp_2,
                ),
            ]
        )
        cache = FailingCache()

        with self.assertRaises(WorkflowExecutionError) as cm:
            dag.execute(cache=cache)

        self.assertEqual(cm.exception.stage_name, "cache_publication")
        self.assertIn("res_1", compensated)
        self.assertIn("res_2", compensated)
        self.assertEqual(cache, {}, "Partial cache entries must be purged")

    async def test_cache_publication_failure_async(self) -> None:
        compensated: list[str] = []

        class FailingCache(dict[tuple[str, str], object]):
            def __setitem__(self, key: tuple[str, str], val: object) -> None:
                if key[0] == "s2":
                    raise OSError("disk full")
                super().__setitem__(key, val)

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        async def comp_1(out: object) -> None:
            compensated.append(str(out))

        async def stage_2(_deps: dict[str, object]) -> str:
            return "res_2"

        async def comp_2(out: object) -> None:
            compensated.append(str(out))

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage(
                    "s2",
                    stage_2,
                    fingerprint="f2",
                    dependencies=("s1",),
                    compensate=comp_2,
                ),
            ]
        )
        cache = FailingCache()

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute(cache=cache)

        self.assertEqual(cm.exception.stage_name, "cache_publication")
        self.assertIn("res_1", compensated)
        self.assertIn("res_2", compensated)
        self.assertEqual(cache, {}, "Partial cache entries must be purged")

    def test_cache_publication_write_then_raise_sync(self) -> None:
        compensated: list[str] = []

        class WriteThenRaiseCache(dict[tuple[str, str], object]):
            def __setitem__(self, key: tuple[str, str], val: object) -> None:
                super().__setitem__(key, val)
                if key[0] == "s2":
                    raise OSError("disk write failed after commit")

        def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        def comp_1(out: object) -> None:
            compensated.append(str(out))

        def stage_2(_deps: dict[str, object]) -> str:
            return "res_2"

        def comp_2(out: object) -> None:
            compensated.append(str(out))

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage(
                    "s2",
                    stage_2,
                    fingerprint="f2",
                    dependencies=("s1",),
                    compensate=comp_2,
                ),
            ]
        )
        cache = WriteThenRaiseCache()

        with self.assertRaises(WorkflowExecutionError) as cm:
            dag.execute(cache=cache)

        self.assertEqual(cm.exception.stage_name, "cache_publication")
        self.assertIn("res_1", compensated)
        self.assertIn("res_2", compensated)
        self.assertEqual(
            cache,
            {},
            "All written cache entries including the raising key must be purged",
        )

    async def test_cache_publication_write_then_raise_async(self) -> None:
        compensated: list[str] = []

        class WriteThenRaiseCache(dict[tuple[str, str], object]):
            def __setitem__(self, key: tuple[str, str], val: object) -> None:
                super().__setitem__(key, val)
                if key[0] == "s2":
                    raise OSError("disk write failed after commit")

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        async def comp_1(out: object) -> None:
            compensated.append(str(out))

        async def stage_2(_deps: dict[str, object]) -> str:
            return "res_2"

        async def comp_2(out: object) -> None:
            compensated.append(str(out))

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, fingerprint="f1", compensate=comp_1),
                WorkflowStage(
                    "s2",
                    stage_2,
                    fingerprint="f2",
                    dependencies=("s1",),
                    compensate=comp_2,
                ),
            ]
        )
        cache = WriteThenRaiseCache()

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute(cache=cache)

        self.assertEqual(cm.exception.stage_name, "cache_publication")
        self.assertIn("res_1", compensated)
        self.assertIn("res_2", compensated)
        self.assertEqual(
            cache,
            {},
            "All written cache entries including the raising key must be purged",
        )

    async def test_async_execute_rollback_timeout_bounds_hung_compensator(
        self,
    ) -> None:
        hung_event = asyncio.Event()

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        async def hung_comp(_out: object) -> None:
            await hung_event.wait()

        async def stage_2(_deps: dict[str, object]) -> str:
            raise RuntimeError("failure triggering compensation")

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, compensate=hung_comp),
                WorkflowStage("s2", stage_2, dependencies=("s1",)),
            ],
            rollback_timeout=0.05,
        )

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute()

        self.assertEqual(cm.exception.stage_name, "s2")
        errors = cm.exception.compensation_errors
        self.assertTrue(any(name == "rollback_timeout" for name, _ in errors))

    def test_workflow_dag_rejects_non_finite_and_invalid_timeouts(self) -> None:
        def dummy(_deps: dict[str, object]) -> int:
            return 1

        stage = WorkflowStage("s1", dummy)
        for invalid in (
            math.nan,
            math.inf,
            -math.inf,
            0,
            0.0,
            -1,
            -0.5,
            True,
            False,
            "1.0",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    WorkflowDAG([stage], rollback_timeout=invalid)  # type: ignore[arg-type]

    async def test_async_execute_rejects_non_finite_and_invalid_timeouts(self) -> None:
        def dummy(_deps: dict[str, object]) -> int:
            return 1

        dag = WorkflowDAG([WorkflowStage("s1", dummy)])
        for invalid in (
            math.nan,
            math.inf,
            -math.inf,
            0,
            0.0,
            -1,
            -0.5,
            True,
            False,
            "1.0",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    await dag.async_execute(rollback_timeout=invalid)  # type: ignore[arg-type]

    async def test_async_execute_rollback_timeout_stops_subsequent_compensators(
        self,
    ) -> None:
        c1_started = False
        hung_event = asyncio.Event()

        async def stage_1(_deps: dict[str, object]) -> str:
            return "res_1"

        async def comp_1(_out: object) -> None:
            nonlocal c1_started
            c1_started = True

        async def stage_2(_deps: dict[str, object]) -> str:
            return "res_2"

        async def comp_2(_out: object) -> None:
            await hung_event.wait()

        async def stage_3(_deps: dict[str, object]) -> str:
            raise RuntimeError("failure triggering compensation")

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1, compensate=comp_1),
                WorkflowStage("s2", stage_2, dependencies=("s1",), compensate=comp_2),
                WorkflowStage("s3", stage_3, dependencies=("s2",)),
            ],
            rollback_timeout=0.03,
        )

        with self.assertRaises(WorkflowExecutionError) as cm:
            await dag.async_execute()

        self.assertEqual(cm.exception.stage_name, "s3")
        self.assertFalse(c1_started)
        errors = cm.exception.compensation_errors
        error_names = [name for name, _ in errors]
        self.assertIn("rollback_timeout", error_names)
        self.assertIn("s2", error_names)
        self.assertIn("s1", error_names)
        s1_err = next(err for name, err in errors if name == "s1")
        self.assertIsInstance(s1_err, asyncio.CancelledError)

    async def test_async_execute_setup_failure_cancels_and_drains_earlier_tasks(
        self,
    ) -> None:
        stage1_ran = False

        async def stage_1(_deps: dict[str, object]) -> str:
            nonlocal stage1_ran
            stage1_ran = True
            return "res_1"

        async def stage_2(_deps: dict[str, object]) -> str:
            return "res_2"

        dag = WorkflowDAG(
            [
                WorkflowStage("s1", stage_1),
                WorkflowStage("s2", stage_2),
            ]
        )

        original_create_task = asyncio.create_task
        task_count = 0

        def failing_create_task(
            coro: object, *args: object, **kwargs: object
        ) -> asyncio.Task[object]:
            nonlocal task_count
            task_count += 1
            if task_count == 2:
                if hasattr(coro, "close"):
                    coro.close()
                raise RuntimeError("simulated task creation failure")
            return original_create_task(coro, *args, **kwargs)  # type: ignore[arg-type]

        asyncio.create_task = failing_create_task  # type: ignore[assignment]
        try:
            with self.assertRaises(RuntimeError) as cm:
                await dag.async_execute()
            self.assertEqual(str(cm.exception), "simulated task creation failure")
        finally:
            asyncio.create_task = original_create_task  # type: ignore[assignment]

        await asyncio.sleep(0.02)
        self.assertFalse(stage1_ran)



class TestGracefulShutdown(unittest.IsolatedAsyncioTestCase):
    async def test_programmatic_shutdown_and_lifo_cleanup(self) -> None:
        shutdown = GracefulShutdown(timeout=1.0)
        self.assertFalse(shutdown.is_shutting_down)

        cleanup_log: list[str] = []

        def sync_cleanup() -> None:
            cleanup_log.append("sync")

        async def async_cleanup() -> None:
            await asyncio.sleep(0.01)
            cleanup_log.append("async")

        shutdown.add_callback(sync_cleanup)
        shutdown.add_callback(async_cleanup)

        shutdown.trigger_shutdown(signum=15)
        self.assertTrue(shutdown.is_shutting_down)
        self.assertEqual(shutdown.signal_received, 15)

        sig = await shutdown.wait_for_shutdown()
        self.assertEqual(sig, 15)

        errors = await shutdown.run_cleanup()
        self.assertEqual(errors, [])
        # Callbacks run in reverse order (LIFO): async then sync
        self.assertEqual(cleanup_log, ["async", "sync"])

    async def test_context_manager(self) -> None:
        async with GracefulShutdown() as shutdown:
            shutdown.add_callback(lambda: setattr(self, "_cleaned", True))
            shutdown.trigger_shutdown(signum=2)
            self.assertTrue(shutdown.is_shutting_down)

        self.assertTrue(getattr(self, "_cleaned", False))

    async def test_cancellation_triggers_cleanup(self) -> None:
        cleanup_called = False

        async def worker() -> None:
            nonlocal cleanup_called
            async with GracefulShutdown() as shutdown:
                shutdown.add_callback(lambda: setattr(self, "_cancelled_clean", True))
                await asyncio.sleep(10.0)

        task = asyncio.create_task(worker())
        await asyncio.sleep(0.01)
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task

        self.assertTrue(getattr(self, "_cancelled_clean", False))


if __name__ == "__main__":
    unittest.main()
