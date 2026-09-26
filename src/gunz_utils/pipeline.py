"""Bounded structured async worker pipelines."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def worker_map(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    workers: int,
    queue_size: int | None = None,
) -> AsyncIterator[R]:
    """Map work through bounded input/output queues with backpressure."""
    if workers < 1:
        raise ValueError("workers must be positive")
    size = queue_size if queue_size is not None else workers * 2
    if size < 1:
        raise ValueError("queue_size must be positive")
    incoming: asyncio.Queue[T | None] = asyncio.Queue(size)
    outgoing: asyncio.Queue[tuple[bool, R | BaseException]] = asyncio.Queue(size)

    async def producer() -> None:
        for item in items:
            await incoming.put(item)
        for _ in range(workers):
            await incoming.put(None)

    async def worker() -> None:
        while True:
            item = await incoming.get()
            if item is None:
                return
            try:
                await outgoing.put((True, await func(item)))
            except BaseException as exc:
                await outgoing.put((False, exc))

    producer_task = asyncio.create_task(producer())
    tasks = [asyncio.create_task(worker()) for _ in range(workers)]
    remaining = workers
    try:
        while remaining:
            if all(task.done() for task in tasks):
                remaining = 0
                break
            ok, value = await outgoing.get()
            if ok:
                yield value  # type: ignore[misc]
            else:
                raise value  # type: ignore[misc]
    finally:
        producer_task.cancel()
        for task in tasks:
            task.cancel()
        await asyncio.gather(producer_task, *tasks, return_exceptions=True)


__all__ = ["worker_map"]
