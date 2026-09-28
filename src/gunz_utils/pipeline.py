"""Bounded structured async worker pipelines."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import TypeVar, cast

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

    async def producer() -> None:
        try:
            for item in items:
                await incoming.put(item)
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            await outgoing.put((False, exc))
        else:
            for _ in range(workers):
                await incoming.put(_DONE)

    async def worker() -> None:
        while True:
            item = await incoming.get()
            if item is _DONE:
                await outgoing.put((True, _DONE))
                return
            try:
                result = await func(cast(T, item))
            except asyncio.CancelledError:
                raise
            except BaseException as exc:
                await outgoing.put((False, exc))
                return
            await outgoing.put((True, result))

    producer_task = asyncio.create_task(producer())
    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    completed = 0
    try:
        while completed < workers:
            ok, value = await outgoing.get()
            if value is _DONE:
                completed += 1
            elif ok:
                yield cast(R, value)
            else:
                raise cast(BaseException, value)
        await producer_task
    finally:
        producer_task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(producer_task, *tasks, return_exceptions=True)


__all__ = ["worker_map"]
