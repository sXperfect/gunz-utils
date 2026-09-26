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
    """Gather awaitables while bounding active task creation."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    iterator = iter(awaitables)
    pending: dict[asyncio.Task[T], int] = {}
    ordered: dict[int, T | BaseException] = {}
    next_index = 0

    def schedule_one() -> bool:
        nonlocal next_index
        try:
            item = next(iterator)
        except StopIteration:
            return False
        pending[asyncio.create_task(item)] = next_index
        next_index += 1
        return True

    for _ in range(limit):
        if not schedule_one():
            break
    try:
        while pending:
            done, _ = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                index = pending.pop(task)
                try:
                    ordered[index] = task.result()
                except BaseException as exc:
                    if not return_exceptions:
                        raise
                    ordered[index] = exc
                schedule_one()
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    return [ordered[index] for index in range(next_index)]


async def map_concurrent(
    func: Callable[[T], Awaitable[R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R | BaseException]:
    """Apply an async function with bounded task creation and ordered results."""
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
