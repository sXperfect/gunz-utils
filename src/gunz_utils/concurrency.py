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


__all__ = ["gather_limited", "map_concurrent"]
