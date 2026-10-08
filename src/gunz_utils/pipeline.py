"""Bounded structured async worker pipelines."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine, Iterable
from typing import Any, TypeVar, cast

T = TypeVar("T")
R = TypeVar("R")
_DONE = object()


async def worker_map(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    workers: int,
    queue_size: int | None = None,
) -> AsyncIterator[R]:
    """Map work through bounded queues, propagating failures and cancellation."""
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise ValueError("workers must be a positive integer")
    if queue_size is not None and (
        isinstance(queue_size, bool)
        or not isinstance(queue_size, int)
        or queue_size < 1
    ):
        raise ValueError("queue_size must be a positive integer or None")
    size = queue_size if queue_size is not None else workers * 2
    incoming: asyncio.Queue[T | object] = asyncio.Queue(size)
    outgoing: asyncio.Queue[tuple[bool, R | BaseException | object]] = asyncio.Queue(
        size
    )
    wake = asyncio.Event()
    started = asyncio.Event()

    async def publish(ok: bool, value: R | BaseException | object) -> None:
        await outgoing.put((ok, value))
        wake.set()

    async def producer() -> None:
        await started.wait()
        try:
            for item in items:
                await incoming.put(item)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            await publish(False, exc)
        else:
            for _ in range(workers):
                await incoming.put(_DONE)

    async def worker() -> None:
        await started.wait()
        while True:
            item = await incoming.get()
            if item is _DONE:
                await publish(True, _DONE)
                return
            try:
                result = await func(cast(T, item))
            except asyncio.CancelledError:
                raise
            except BaseException as exc:
                await publish(False, exc)
                return
            await publish(True, result)

    tasks: list[asyncio.Task[None]] = []

    def submit(coroutine: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        try:
            task = asyncio.create_task(coroutine)
        except BaseException:
            coroutine.close()
            raise
        tasks.append(task)
        task.add_done_callback(lambda _task: wake.set())
        return task

    completed = 0
    failure: BaseException | None = None
    try:
        producer_task = submit(producer())
        for _ in range(workers):
            submit(worker())
        started.set()
        while completed < workers:
            wake.clear()
            # Child cancellation has no queue message. Observe terminal task
            # outcomes before awaiting another result, including simultaneous
            # cancellation and result publication.
            for task in tasks:
                if task.done():
                    task.result()
            try:
                ok, value = outgoing.get_nowait()
            except asyncio.QueueEmpty:
                await wake.wait()
                continue
            if value is _DONE:
                completed += 1
            elif ok:
                yield cast(R, value)
            else:
                raise cast(BaseException, value)
        await producer_task
    except BaseException as exc:
        failure = exc
        raise
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            drain = asyncio.gather(*tasks, return_exceptions=True)
            cleanup_cancelled: asyncio.CancelledError | None = None
            while not drain.done():
                try:
                    await asyncio.shield(drain)
                except asyncio.CancelledError as exc:
                    cleanup_cancelled = exc
            if failure is None and cleanup_cancelled is not None:
                raise cleanup_cancelled


__all__ = ["worker_map"]
