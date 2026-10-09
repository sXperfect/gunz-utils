"""Bounded asynchronous concurrency helpers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable
from typing import Any, TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def _cancel_and_drain(
    tasks: Iterable[asyncio.Task[Any]],
) -> asyncio.CancelledError | None:
    """Cancel owned tasks once and finish their cooperative cleanup."""
    owned = tuple(tasks)
    for task in owned:
        if not task.done():
            task.cancel()
    if not owned:
        return None
    drain = asyncio.gather(*owned, return_exceptions=True)
    cancelled: asyncio.CancelledError | None = None
    while not drain.done():
        try:
            await asyncio.shield(drain)
        except asyncio.CancelledError as exc:
            cancelled = exc
    return cancelled


async def gather_limited(
    awaitables: Iterable[Coroutine[Any, Any, T]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[T | BaseException]:
    """Gather awaitables while bounding active task creation."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if not isinstance(return_exceptions, bool):
        raise ValueError("return_exceptions must be bool")
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
        try:
            task = asyncio.create_task(item)
        except BaseException:
            item.close()
            raise
        pending[task] = next_index
        next_index += 1
        return True

    failure: BaseException | None = None
    try:
        for _ in range(limit):
            if not schedule_one():
                break
        while pending:
            done, _ = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                index = pending.pop(task)
                try:
                    ordered[index] = task.result()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if not return_exceptions:
                        raise
                    ordered[index] = exc
                schedule_one()
    except BaseException as exc:
        failure = exc
        raise
    finally:
        cancelled = await _cancel_and_drain(pending)
        if failure is None and cancelled is not None:
            raise cancelled
    return [ordered[index] for index in range(next_index)]


async def map_concurrent(
    func: Callable[[T], Coroutine[Any, Any, R]],
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
    func: Callable[[T], Coroutine[Any, Any, R]],
    items: Iterable[T],
    *,
    limit: int,
) -> AsyncIterator[R]:
    """Yield mapping results as soon as each bounded task completes."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    iterator = iter(items)
    active: set[asyncio.Task[R]] = set()

    def schedule_one() -> bool:
        try:
            item = next(iterator)
        except StopIteration:
            return False
        coroutine = func(item)
        try:
            task = asyncio.create_task(coroutine)
        except BaseException:
            coroutine.close()
            raise
        active.add(task)
        return True

    failure: BaseException | None = None
    try:
        for _ in range(limit):
            if not schedule_one():
                break
        while active:
            done, _ = await asyncio.wait(
                active,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                active.discard(task)
                yield task.result()
                schedule_one()
    except BaseException as exc:
        failure = exc
        raise
    finally:
        cancelled = await _cancel_and_drain(active)
        if cancelled is not None and (
            failure is None or isinstance(failure, GeneratorExit)
        ):
            raise cancelled


__all__ = ["gather_limited", "map_concurrent", "map_unordered"]
