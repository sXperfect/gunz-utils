"""Bounded asynchronous concurrency helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import pickle
from itertools import chain, islice
from collections.abc import AsyncIterator, Callable, Coroutine, Iterable, Iterator
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
    """Gather awaitables while bounding active task creation.

    Parameters
    ----------
    awaitables : Iterable[Coroutine[Any, Any, T]]
        awaitables parameter.
    limit : int
        limit parameter.
    return_exceptions : bool
        return_exceptions parameter.

    Returns
    -------
    list[T | BaseException]
        The result of the operation.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    if not isinstance(return_exceptions, bool):
        raise ValueError("return_exceptions must be bool")
    iterator = iter(awaitables)
    pending: dict[asyncio.Task[T], int] = {}
    ordered: dict[int, T | BaseException] = {}
    next_index = 0

    def schedule_one() -> bool:
        """schedule_one() function.

        Returns
        -------
        bool
            The result of the operation.
        """
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
    """Apply an async function with bounded task creation and ordered results.

    Parameters
    ----------
    func : Callable[[T], Coroutine[Any, Any, R]]
        func parameter.
    items : Iterable[T]
        items parameter.
    limit : int
        limit parameter.
    return_exceptions : bool
        return_exceptions parameter.

    Returns
    -------
    list[R | BaseException]
        The result of the operation.
    """
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
    """Yield mapping results as soon as each bounded task completes.

    Parameters
    ----------
    func : Callable[[T], Coroutine[Any, Any, R]]
        func parameter.
    items : Iterable[T]
        items parameter.
    limit : int
        limit parameter.

    Returns
    -------
    AsyncIterator[R]
        The result of the operation.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    iterator = iter(items)
    active: set[asyncio.Task[R]] = set()

    def schedule_one() -> bool:
        """schedule_one() function.

        Returns
        -------
        bool
            The result of the operation.
        """
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


def process_map(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    chunksize: int | None = None,
    threshold: int = 8,
    fallback_serial: bool = True,
) -> list[R]:
    """Execute a CPU-bound callable over an iterable using multi-processing.

    For small workloads (<= threshold items) or when workers <= 1, work runs
    serially in the current process to eliminate process spawning and IPC
    overhead. When workers > 1, tasks execute across worker processes with
    graceful cleanup on interruption or cancellation.

    Parameters
    ----------
    func : Callable[[T], R]
        Picklable top-level function to map over each item.
    items : Iterable[T]
        Collection of items to process.
    workers : int | None, optional
        Number of worker processes. Defaults to None (auto-detect up to CPU count).
    chunksize : int | None, optional
        Number of items per IPC batch. Defaults to auto-chunked.
    threshold : int, optional
        Minimum item count required to spawn worker processes. Defaults to 8.
    fallback_serial : bool, optional
        If True, falls back to serial execution if process pool spawning
        or pickling fails. Defaults to True.

    Returns
    -------
    list[R]
        Ordered results matching the input items.
    """
    item_list = list(items) if not isinstance(items, list) else items
    total = len(item_list)

    if workers is not None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError("workers must be a positive integer or None")

    if chunksize is not None:
        if (
            isinstance(chunksize, bool)
            or not isinstance(chunksize, int)
            or chunksize < 1
        ):
            raise ValueError("chunksize must be a positive integer or None")

    if total == 0:
        return []
    if total <= threshold or workers == 1:
        return [func(item) for item in item_list]

    max_workers = workers
    if max_workers is None:
        cpu_count = os.cpu_count() or 1
        max_workers = min(total, cpu_count)
        if max_workers <= 1:
            return [func(item) for item in item_list]

    calc_chunksize = chunksize
    if calc_chunksize is None:
        calc_chunksize = max(1, total // (max_workers * 4))

    # Detect unsupported callables before any worker executes. Never replay
    # a partially executed workload after a worker or pool failure.
    if fallback_serial:
        try:
            pickle.dumps(func)
        except (pickle.PickleError, AttributeError, TypeError):
            return [func(item) for item in item_list]
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=max_workers
    ) as executor:
        return list(executor.map(func, item_list, chunksize=calc_chunksize))


def process_imap(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    chunksize: int | None = None,
    threshold: int = 8,
    fallback_serial: bool = True,
) -> Iterator[R]:
    """Yield results from a CPU-bound callable executed across worker processes.

    Results are yielded in input order as chunks finish. For small workloads
    (<= threshold) or when workers <= 1, items run lazily in the current process.

    Parameters
    ----------
    func : Callable[[T], R]
        Picklable top-level function.
    items : Iterable[T]
        Collection of items.
    workers : int | None, optional
        Worker process count.
    chunksize : int | None, optional
        Items per batch.
    threshold : int, optional
        Threshold for multiprocessing. Defaults to 8.
    fallback_serial : bool, optional
        Fallback to serial on pool errors. Defaults to True.

    Yields
    ------
    R
        Mapped results.
    """
    if workers is not None:
        if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
            raise ValueError("workers must be a positive integer or None")
    if chunksize is not None:
        if isinstance(chunksize, bool) or not isinstance(chunksize, int) or chunksize < 1:
            raise ValueError("chunksize must be a positive integer or None")
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
        raise ValueError("threshold must be a non-negative integer")

    iterator = iter(items)
    if workers == 1:
        for item in iterator:
            yield func(item)
        return

    # Look ahead only enough to select the serial fast path. In particular,
    # never materialize a generator just to discover its length.
    prefix = list(islice(iterator, threshold + 1))
    if len(prefix) <= threshold:
        for item in prefix:
            yield func(item)
        return

    max_workers = workers or (os.cpu_count() or 1)
    if max_workers <= 1:
        for item in chain(prefix, iterator):
            yield func(item)
        return

    if fallback_serial:
        try:
            pickle.dumps(func)
        except (pickle.PickleError, AttributeError, TypeError):
            for item in chain(prefix, iterator):
                yield func(item)
            return

    # Executor.map eagerly submits the supplied iterable in some Python
    # versions. Feed finite windows to guarantee bounded submission on all
    # supported interpreters, preserving ordering within and across windows.
    batch_size = chunksize or 1
    window_size = max_workers * batch_size * 2
    remaining = chain(prefix, iterator)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        while batch := list(islice(remaining, window_size)):
            yield from executor.map(func, batch, chunksize=batch_size)


__all__ = [
    "gather_limited",
    "map_concurrent",
    "map_unordered",
    "process_map",
    "process_imap",
]
