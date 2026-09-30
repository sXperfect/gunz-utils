"""Tests for autonomous agent loop and distributed worker execution primitives."""

from __future__ import annotations

import asyncio
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
        cleanup_called = False

        async with GracefulShutdown() as shutdown:
            shutdown.add_callback(lambda: setattr(self, "_cleaned", True))
            shutdown.trigger_shutdown(signum=2)
            self.assertTrue(shutdown.is_shutting_down)

        self.assertTrue(getattr(self, "_cleaned", False))


if __name__ == "__main__":
    unittest.main()
