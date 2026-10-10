"""Ownership and terminal-signal regressions for bounded worker pipelines."""

from __future__ import annotations

import asyncio
import gc
import warnings
from collections.abc import AsyncGenerator, Coroutine, Iterator
from typing import Any, cast

import pytest

from gunz_utils.pipeline import worker_map


@pytest.mark.parametrize("rejected_submission", [1, 2, 4])
def test_partial_setup_closes_coroutine_and_drains_tasks(
    monkeypatch: pytest.MonkeyPatch, rejected_submission: int
) -> None:
    async def scenario() -> None:
        original = asyncio.create_task
        created: list[asyncio.Task[None]] = []
        submissions = 0
        invoked: list[int] = []
        failure = RuntimeError("task submission rejected")

        def submit(coroutine: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
            nonlocal submissions
            submissions += 1
            if submissions == rejected_submission:
                raise failure
            task = original(coroutine)
            created.append(task)
            return task

        async def operation(value: int) -> int:
            invoked.append(value)
            await asyncio.Event().wait()
            return value

        stream = worker_map(operation, range(20), workers=3, queue_size=1)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            with monkeypatch.context() as scope:
                scope.setattr(asyncio, "create_task", submit)
                with pytest.raises(RuntimeError) as observed:
                    await anext(stream)
            gc.collect()
            await asyncio.sleep(0)
        assert observed.value is failure
        assert all(task.done() for task in created)
        assert invoked == []
        assert not [w for w in captured if "never awaited" in str(w.message)]

    asyncio.run(scenario())


@pytest.mark.parametrize("cancel_source", ["worker", "producer"])
def test_child_self_cancellation_propagates_and_drains(cancel_source: str) -> None:
    async def scenario() -> None:
        baseline = asyncio.all_tasks()

        def source() -> Iterator[int]:
            if cancel_source == "producer":
                raise asyncio.CancelledError("producer self-cancelled")
            yield 1

        async def operation(value: int) -> int:
            raise asyncio.CancelledError("worker self-cancelled")

        stream = worker_map(operation, source(), workers=2, queue_size=1)
        with pytest.raises(
            asyncio.CancelledError, match=f"{cancel_source} self-cancelled"
        ):
            await asyncio.wait_for(anext(stream), timeout=1)
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())


def test_repeated_caller_cancellation_waits_for_owned_cleanup() -> None:
    async def scenario() -> None:
        baseline = asyncio.all_tasks()
        operation_started = asyncio.Event()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        cleaned = False

        async def operation(value: int) -> int:
            nonlocal cleaned
            operation_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release_cleanup.wait()
                cleaned = True
            return value

        stream = worker_map(operation, range(20), workers=1, queue_size=1)
        consumer = asyncio.ensure_future(anext(stream))
        await operation_started.wait()
        consumer.cancel("original caller cancellation")
        await cleanup_started.wait()
        consumer.cancel("second caller cancellation")
        await asyncio.sleep(0)
        assert not consumer.done()
        release_cleanup.set()
        with pytest.raises(
            asyncio.CancelledError, match="original caller cancellation"
        ):
            await consumer
        assert cleaned
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())


def test_simultaneous_result_and_cancellation_propagates_cancellation() -> None:
    async def scenario() -> None:
        barrier = asyncio.Event()
        both_started = asyncio.Event()
        started = 0

        async def operation(value: int) -> int:
            nonlocal started
            started += 1
            if started == 2:
                both_started.set()
            await barrier.wait()
            if value == 1:
                raise asyncio.CancelledError("simultaneous child cancellation")
            return value

        stream = worker_map(operation, [0, 1], workers=2, queue_size=2)
        consumer = asyncio.ensure_future(anext(stream))
        await both_started.wait()
        barrier.set()
        with pytest.raises(
            asyncio.CancelledError, match="simultaneous child cancellation"
        ):
            await consumer

    asyncio.run(scenario())


def test_early_close_with_full_queues_drains_owned_tasks() -> None:
    async def scenario() -> None:
        baseline = asyncio.all_tasks()
        active = 0
        peak = 0

        async def operation(value: int) -> int:
            nonlocal active, peak
            active += 1
            peak = max(active, peak)
            try:
                await asyncio.sleep(0)
                return value
            finally:
                active -= 1

        stream = cast(
            AsyncGenerator[int, None],
            worker_map(operation, range(100), workers=3, queue_size=1),
        )
        await anext(stream)
        await stream.aclose()
        assert peak <= 3
        assert active == 0
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())
