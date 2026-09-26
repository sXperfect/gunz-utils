"""Bounded asynchronous concurrency helpers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def gather_limited(
    awaitables: Iterable[Awaitable[T]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[T | BaseException]:
    """Gather awaitables while limiting the number executing concurrently."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    semaphore = asyncio.Semaphore(limit)

    async def run(item: Awaitable[T]) -> T:
        async with semaphore:
            return await item

    return list(
        await asyncio.gather(
            *(run(item) for item in awaitables),
            return_exceptions=return_exceptions,
        )
    )


async def map_concurrent(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R | BaseException]:
    """Apply an async function concurrently with bounded parallelism."""
    return await gather_limited(
        (func(item) for item in items),
        limit=limit,
        return_exceptions=return_exceptions,
    )


async def map_unordered(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    limit: int,
) -> AsyncIterator[R]:
    """Yield mapping results as soon as each bounded task completes."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    iterator = iter(items)
    pending: set[asyncio.Task[R]] = set()

    def schedule_one() -> bool:
        try:
            item = next(iterator)
        except StopIteration:
            return False
        pending.add(asyncio.create_task(func(item)))
        return True

    for _ in range(limit):
        if not schedule_one():
            break
    try:
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                yield task.result()
                schedule_one()
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)


__all__ = ["gather_limited", "map_concurrent", "map_unordered"]
