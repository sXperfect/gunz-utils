"""Failure cleanup must retain task ownership without pulling new lazy work."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio
import gc
import inspect
import unittest
from collections.abc import Coroutine, Iterator
from typing import Any
from unittest.mock import patch

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.concurrency import (
    as_completed_limited,
    gather_limited,
    map_concurrent,
)


class WorkerFailure(RuntimeError):
    """Failure from work that was actually scheduled."""


class ProducerFailure(RuntimeError):
    """Failure from pulling work after a worker failed."""


class TestAsyncCleanup(unittest.IsolatedAsyncioTestCase):
    async def test_lazy_gather_does_not_pull_after_worker_failure(self) -> None:
        pulled: list[int] = []
        closed: list[bool] = []

        async def fail() -> int:
            raise WorkerFailure("worker")

        def source() -> Iterator[Coroutine[Any, Any, int]]:
            try:
                pulled.append(0)
                yield fail()
                pulled.append(1)
                raise ProducerFailure("must not pull")
            finally:
                closed.append(True)

        with self.assertRaises(WorkerFailure):
            await gather_limited(source(), limit=1)
        self.assertEqual(pulled, [0])
        self.assertEqual(closed, [True])

    async def test_failed_mapping_does_not_invoke_unscheduled_factories(self) -> None:
        called: list[int] = []

        async def fail() -> int:
            raise WorkerFailure("worker")

        def factory(
            value: int,
        ) -> Coroutine[Any, Any, int]:
            called.append(value)
            return fail()

        with self.assertRaises(WorkerFailure):
            await map_concurrent(factory, range(5), limit=1)
        self.assertEqual(called, [0])

    async def test_completed_iterator_does_not_pull_during_cleanup(self) -> None:
        pulled: list[int] = []

        async def fail() -> int:
            raise WorkerFailure("worker")

        def source() -> Iterator[Coroutine[Any, Any, int]]:
            for index in range(5):
                pulled.append(index)
                yield fail()

        with self.assertRaises(WorkerFailure):
            async for _ in as_completed_limited(source(), limit=1):
                pass
        self.assertEqual(pulled, [0])

    async def test_producer_error_cannot_bypass_owned_task_cleanup(self) -> None:
        tasks: list[asyncio.Task[Any]] = []
        finished = asyncio.Event()

        async def fail() -> int:
            await asyncio.sleep(0)
            raise WorkerFailure("worker")

        async def slow() -> int:
            task = asyncio.current_task()
            if task is not None:
                tasks.append(task)
            try:
                await asyncio.Event().wait()
                return 0
            finally:
                finished.set()

        class Source:
            def __init__(self) -> None:
                self.index = 0

            def __iter__(self) -> Source:
                return self

            def __next__(self) -> Coroutine[Any, Any, int]:
                self.index += 1
                if self.index == 1:
                    return fail()
                if self.index == 2:
                    return slow()
                raise ProducerFailure("must not pull")

        try:
            with self.assertRaises(WorkerFailure):
                await gather_limited(Source(), limit=2)
            self.assertTrue(finished.is_set())
            self.assertTrue(all(task.done() for task in tasks))
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def test_completed_batch_exceptions_are_all_observed(self) -> None:
        loop = asyncio.get_running_loop()
        previous = loop.get_exception_handler()
        errors: list[dict[str, Any]] = []
        original_wait = asyncio.wait

        async def wait_all(
            tasks: Any,
            **kwargs: Any,
        ) -> Any:
            return await original_wait(tasks, return_when=asyncio.ALL_COMPLETED)

        async def fail(
            value: int,
        ) -> int:
            raise WorkerFailure(str(value))

        loop.set_exception_handler(lambda _loop, context: errors.append(context))
        try:
            with patch("gunz_utils.concurrency.asyncio.wait", wait_all):
                with self.assertRaises(WorkerFailure):
                    async for _ in as_completed_limited(
                        [fail(1), fail(2)], limit=2
                    ):
                        pass
            gc.collect()
            await asyncio.sleep(0)
            unobserved = [
                context for context in errors
                if "was never retrieved" in str(context.get("message", ""))
            ]
            self.assertEqual(unobserved, [])
        finally:
            loop.set_exception_handler(previous)

    async def test_unused_sequence_coroutines_are_closed(self) -> None:
        async def fail() -> int:
            raise WorkerFailure("worker")

        for completed in [False, True]:
            coroutines = [fail(), fail(), fail()]
            with self.assertRaises(WorkerFailure):
                if completed:
                    async for _ in as_completed_limited(coroutines, limit=1):
                        pass
                else:
                    await gather_limited(coroutines, limit=1)
            self.assertTrue(all(
                inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
                for coro in coroutines
            ))

    async def test_wrong_coroutine_type_preserves_type_error(self) -> None:
        with self.assertRaises(TypeError):
            await gather_limited([123], limit=1)  # type: ignore[arg-type]

    async def test_iterator_close_error_preserves_worker_failure(self) -> None:
        async def fail() -> int:
            raise WorkerFailure("worker")

        def source() -> Iterator[Coroutine[Any, Any, int]]:
            try:
                yield fail()
            finally:
                raise ProducerFailure("close failure")

        with self.assertRaises(WorkerFailure) as caught:
            await gather_limited(source(), limit=1)
        self.assertIn("ProducerFailure", " ".join(caught.exception.__notes__))

    async def test_repeated_cancellation_waits_for_worker_cleanup(self) -> None:
        entered = asyncio.Event()
        cleaning = asyncio.Event()
        release = asyncio.Event()
        finished = asyncio.Event()

        async def slow() -> int:
            entered.set()
            try:
                await asyncio.Event().wait()
                return 0
            finally:
                cleaning.set()
                await release.wait()
                finished.set()

        async def consume() -> None:
            async for _ in as_completed_limited([slow()], limit=1):
                pass

        consumer = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            consumer.cancel()
            await asyncio.wait_for(cleaning.wait(), timeout=1)
            consumer.cancel()
            await asyncio.sleep(0)
            self.assertFalse(consumer.done())
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(consumer, timeout=1)
            self.assertTrue(finished.is_set())
        finally:
            release.set()
            consumer.cancel()
            await asyncio.gather(consumer, return_exceptions=True)
