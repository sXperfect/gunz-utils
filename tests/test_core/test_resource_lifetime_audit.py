"""Finite resource ownership regressions and GC evidence for async coordinators."""

from __future__ import annotations

import asyncio
import errno
import gc
import os
import weakref
from collections.abc import AsyncGenerator, AsyncIterator, Coroutine, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import CoroutineType
from typing import Any, cast

import pytest

from gunz_utils.cache import SingleFlight, async_ttl_cache, ttl_cache
from gunz_utils.concurrency import gather_limited, map_unordered
from gunz_utils.dag import WorkflowDAG, WorkflowStage
from gunz_utils.pipeline import worker_map
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup
from gunz_utils.subprocess import run_command, run_command_async


@dataclass(slots=True, weakref_slot=True)
class _Payload:
    data: bytearray


def _payload(refs: list[weakref.ReferenceType[_Payload]]) -> _Payload:
    value = _Payload(bytearray(1024))
    refs.append(weakref.ref(value))
    return value


@pytest.mark.parametrize("kind", ["gather", "unordered"])
def test_consumed_coroutine_is_closed_if_task_submission_fails(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    async def scenario() -> None:
        submitted: list[Coroutine[Any, Any, int]] = []
        failure = RuntimeError("synthetic task submission refusal")

        def reject(coroutine: Coroutine[Any, Any, int]) -> asyncio.Task[int]:
            submitted.append(coroutine)
            raise failure

        async def work(value: int) -> int:
            return value

        try:
            with monkeypatch.context() as scope:
                scope.setattr(asyncio, "create_task", reject)
                with pytest.raises(RuntimeError) as observed:
                    if kind == "gather":
                        await gather_limited((work(value) for value in [1]), limit=1)
                    else:
                        await anext(map_unordered(work, [1], limit=1))
            assert observed.value is failure
            assert len(submitted) == 1
            # Native coroutine introspection, independent of library bookkeeping.
            assert isinstance(submitted[0], CoroutineType)
            assert submitted[0].cr_frame is None
        finally:
            for coroutine in submitted:
                coroutine.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["gather", "unordered"])
def test_repeated_caller_cancellation_does_not_interrupt_fd_cleanup(
    tmp_path: Path,
    kind: str,
) -> None:
    async def scenario() -> None:
        path = tmp_path / "synthetic-resource"
        path.write_bytes(b"synthetic")
        descriptor = os.open(path, os.O_RDONLY)
        entered = asyncio.Event()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        consumer: asyncio.Future[Any] | None = None

        async def work(value: int) -> int:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release_cleanup.wait()
                os.close(descriptor)
            return value

        try:
            if kind == "gather":
                consumer = asyncio.ensure_future(
                    gather_limited((work(1) for _ in [1]), limit=1)
                )
            else:
                consumer = asyncio.ensure_future(
                    anext(map_unordered(work, [1], limit=1))
                )
            await asyncio.wait_for(entered.wait(), timeout=1)
            consumer.cancel("initial cancellation")
            await asyncio.wait_for(cleanup_started.wait(), timeout=1)
            consumer.cancel("repeat cancellation")
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError, match="initial cancellation"):
                await asyncio.wait_for(consumer, timeout=1)
            with pytest.raises(OSError) as closed:
                os.fstat(descriptor)
            assert closed.value.errno == errno.EBADF
        finally:
            release_cleanup.set()
            if consumer is not None and not consumer.done():
                consumer.cancel()
                await asyncio.wait_for(
                    asyncio.gather(consumer, return_exceptions=True), 1
                )
            try:
                os.close(descriptor)
            except OSError:
                pass

    asyncio.run(scenario())


def test_sync_cache_eviction_and_clear_release_payloads() -> None:
    refs: list[weakref.ReferenceType[_Payload]] = []

    @ttl_cache(ttl=60, maxsize=2)
    def work(index: int) -> _Payload:
        return _payload(refs)

    for index in range(8):
        work(index)
    gc.collect()
    assert sum(ref() is not None for ref in refs) == 2
    assert work.cache_info().size == 2
    work.cache_clear()
    gc.collect()
    assert all(ref() is None for ref in refs)


def test_async_cache_eviction_and_clear_release_payloads() -> None:
    async def scenario() -> None:
        refs: list[weakref.ReferenceType[_Payload]] = []
        baseline = asyncio.all_tasks()

        @async_ttl_cache(ttl=60, maxsize=2)
        async def work(index: int) -> _Payload:
            return _payload(refs)

        for index in range(8):
            await work(index)
        await asyncio.sleep(0)
        gc.collect()
        assert sum(ref() is not None for ref in refs) == 2
        await work.cache_clear()
        await asyncio.sleep(0)
        gc.collect()
        assert all(ref() is None for ref in refs)
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())


def test_singleflight_cancelled_waiters_release_completed_worker_payload() -> None:
    async def scenario() -> None:
        refs: list[weakref.ReferenceType[_Payload]] = []
        flight = SingleFlight()
        entered = asyncio.Event()
        release = asyncio.Event()
        baseline = asyncio.all_tasks()

        async def work() -> _Payload:
            entered.set()
            await release.wait()
            return _payload(refs)

        callers = [asyncio.create_task(flight.run("one", work)) for _ in range(3)]
        await asyncio.wait_for(entered.wait(), 1)
        for caller in callers:
            caller.cancel()
        await asyncio.gather(*callers, return_exceptions=True)
        producers = list(flight._tasks.values())
        assert len(producers) == 1  # Intentional producer ownership survives waiters.
        release.set()
        await asyncio.wait_for(asyncio.gather(*producers), 1)
        del caller, callers, producers
        await asyncio.sleep(0)
        gc.collect()
        assert flight._tasks == {}
        assert all(ref() is None for ref in refs)
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())


def test_pipeline_close_releases_queued_and_yielded_payloads() -> None:
    async def scenario() -> None:
        refs: list[weakref.ReferenceType[_Payload]] = []
        baseline = asyncio.all_tasks()

        async def work(index: int) -> _Payload:
            await asyncio.sleep(0)
            return _payload(refs)

        stream = cast(
            AsyncGenerator[_Payload, None],
            worker_map(work, range(12), workers=2, queue_size=1),
        )
        await anext(stream)
        await stream.aclose()
        await asyncio.sleep(0)
        gc.collect()
        assert all(ref() is None for ref in refs)
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())


def test_dag_cancelled_execution_releases_compensated_output() -> None:
    async def scenario() -> None:
        refs: list[weakref.ReferenceType[_Payload]] = []
        running = asyncio.Event()
        compensated = asyncio.Event()
        baseline = asyncio.all_tasks()

        async def first(dependencies: Any) -> _Payload:
            return _payload(refs)

        async def second(dependencies: Any) -> None:
            running.set()
            await asyncio.Event().wait()

        async def compensate(value: Any) -> None:
            compensated.set()

        dag = WorkflowDAG(
            [
                WorkflowStage("first", first, compensate=compensate),
                WorkflowStage("second", second, dependencies=("first",)),
            ]
        )
        consumer = asyncio.create_task(dag.async_execute())
        await asyncio.wait_for(running.wait(), 1)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(consumer, 1)
        assert compensated.is_set()
        del consumer
        await asyncio.sleep(0)
        gc.collect()
        assert all(ref() is None for ref in refs)
        assert asyncio.all_tasks() == baseline

    asyncio.run(scenario())


def test_resource_groups_drop_completed_exit_callbacks_and_payloads() -> None:
    refs: list[weakref.ReferenceType[_Payload]] = []

    @contextmanager
    def resource() -> Iterator[_Payload]:
        value = _payload(refs)
        yield value

    group = ResourceGroup()
    for _ in range(4):
        with group:
            group.enter(resource())
    gc.collect()
    assert all(ref() is None for ref in refs)

    async def scenario() -> None:
        @asynccontextmanager
        async def resource_async() -> AsyncIterator[_Payload]:
            value = _payload(refs)
            yield value

        group_async = AsyncResourceGroup()
        for _ in range(4):
            async with group_async:
                await group_async.enter(resource_async())
        gc.collect()
        assert all(ref() is None for ref in refs)

    asyncio.run(scenario())


@pytest.mark.skipif(
    not Path("/proc/self/fd").is_dir(), reason="actual Linux descriptor inventory"
)
def test_repeated_sync_async_child_runs_release_file_descriptors() -> None:
    import sys

    def descriptor_count() -> int:
        return len(os.listdir("/proc/self/fd"))

    baseline = descriptor_count()
    for _ in range(4):
        run_command(
            [sys.executable, "-c", "print('synthetic')"],
            timeout=2,
            max_output_bytes=4096,
        )
    gc.collect()
    assert descriptor_count() == baseline

    async def scenario() -> None:
        # Warm up the event loop/child watcher before comparing descriptors.
        await run_command_async(
            [sys.executable, "-c", "print('warmup')"], timeout=2, max_output_bytes=4096
        )
        before = descriptor_count()
        for _ in range(4):
            await run_command_async(
                [sys.executable, "-c", "print('synthetic')"],
                timeout=2,
                max_output_bytes=4096,
            )
        await asyncio.sleep(0)
        gc.collect()
        assert descriptor_count() == before

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["singleflight", "async-cache"])
def test_internal_producer_coroutine_is_closed_on_submission_failure(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    async def scenario() -> None:
        submitted: list[Coroutine[Any, Any, Any]] = []
        failure = RuntimeError("synthetic producer submission refusal")

        def reject(coroutine: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
            submitted.append(coroutine)
            raise failure

        async def work() -> int:
            return 1

        cached = async_ttl_cache(ttl=1)(work)
        flight = SingleFlight()
        try:
            with monkeypatch.context() as scope:
                scope.setattr(asyncio, "create_task", reject)
                with pytest.raises(RuntimeError) as observed:
                    if kind == "singleflight":
                        await flight.run("synthetic", work)
                    else:
                        await cached()
            assert observed.value is failure
            assert len(submitted) == 1
            assert isinstance(submitted[0], CoroutineType)
            assert submitted[0].cr_frame is None
        finally:
            for coroutine in submitted:
                coroutine.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("kind", ["gather", "unordered"])
def test_cleanup_cancellation_preserves_initiating_worker_failure(kind: str) -> None:
    async def scenario() -> None:
        entered = asyncio.Event()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        failure = RuntimeError("original synthetic worker failure")
        cleaned = False
        baseline = asyncio.all_tasks()

        async def work(value: int) -> int:
            nonlocal cleaned
            if value == 1:
                await entered.wait()
                raise failure
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release_cleanup.wait()
                cleaned = True
            return value

        consumer: asyncio.Future[Any]
        if kind == "gather":
            consumer = asyncio.ensure_future(
                gather_limited((work(v) for v in [0, 1]), limit=2)
            )
        else:
            consumer = asyncio.ensure_future(
                anext(map_unordered(work, [0, 1], limit=2))
            )
        try:
            await asyncio.wait_for(cleanup_started.wait(), 1)
            consumer.cancel("cancellation during failure cleanup")
            await asyncio.sleep(0)
            assert not consumer.done()
            release_cleanup.set()
            with pytest.raises(RuntimeError) as observed:
                await asyncio.wait_for(consumer, 1)
            assert observed.value is failure
            assert cleaned
            assert asyncio.all_tasks() == baseline
        finally:
            release_cleanup.set()
            if not consumer.done():
                consumer.cancel()
                await asyncio.wait_for(
                    asyncio.gather(consumer, return_exceptions=True), 1
                )

    asyncio.run(scenario())


def test_unordered_explicit_close_retains_new_cancellation_after_cleanup(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        path = tmp_path / "close-resource"
        path.write_bytes(b"synthetic")
        descriptor = os.open(path, os.O_RDONLY)
        entered = asyncio.Event()
        cleanup_started = asyncio.Event()
        release_cleanup = asyncio.Event()
        baseline = asyncio.all_tasks()

        async def work(value: int) -> int:
            if value == 0:
                await entered.wait()
                return value
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release_cleanup.wait()
                os.close(descriptor)
            return value

        stream = cast(AsyncGenerator[int, None], map_unordered(work, [0, 1], limit=2))
        closer: asyncio.Future[Any] | None = None
        try:
            assert await asyncio.wait_for(anext(stream), 1) == 0
            closer = asyncio.ensure_future(stream.aclose())
            await asyncio.wait_for(cleanup_started.wait(), 1)
            closer.cancel("close interrupted")
            release_cleanup.set()
            with pytest.raises(asyncio.CancelledError, match="close interrupted"):
                await asyncio.wait_for(closer, 1)
            with pytest.raises(OSError) as observed:
                os.fstat(descriptor)
            assert observed.value.errno == errno.EBADF
            assert asyncio.all_tasks() == baseline
        finally:
            release_cleanup.set()
            if closer is not None and not closer.done():
                closer.cancel()
                await asyncio.wait_for(
                    asyncio.gather(closer, return_exceptions=True), 1
                )
            await stream.aclose()
            try:
                os.close(descriptor)
            except OSError:
                pass

    asyncio.run(scenario())
