"""Bounded asynchronous concurrency helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
# isort: split

from __future__ import annotations

import asyncio
import concurrent.futures
import os

#? Import only the encoding failure type; no deserializer is used here.
from _pickle import PicklingError
from collections.abc import (
    AsyncIterator,
    Callable,
    Coroutine,
    Iterable,
    Iterator,
    Sequence,
)
from itertools import chain
from multiprocessing.reduction import ForkingPickler
from typing import Any, Literal, TypeVar, overload

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


async def _finish_coroutines(
    coroutines: Iterable[Coroutine[Any, Any, T]],
    iterator: Iterator[Coroutine[Any, Any, T]],
    tasks: Iterable[asyncio.Task[Any]],
    failure: BaseException | None,
) -> None:
    """Close unused sequence coroutines and drain all tasks already owned.

    Parameters
    ----------
    coroutines : Iterable[Coroutine[Any, Any, T]]
        Original input, used to distinguish already-created sequences.
    iterator : Iterator[Coroutine[Any, Any, T]]
        Input iterator at its current position.
    tasks : Iterable[asyncio.Task[Any]]
        Owned tasks, including unobserved completed siblings.
    failure : BaseException | None
        Existing failure to preserve while performing cooperative cleanup.

    Returns
    -------
    None
        Completes cleanup or propagates cancellation/finalization failure.

    Notes
    -----
    Never pull a lazy producer during cleanup. Its remaining work has not been
    acquired. Finite sequences may already hold created coroutines, which must
    be closed. Iterator finalization errors cannot bypass task draining or mask
    an existing worker failure or cancellation.
    """
    cleanup_error: BaseException | None = None
    try:
        if isinstance(coroutines, Sequence):
            for remaining in iterator:
                if asyncio.iscoroutine(remaining):
                    remaining.close()
        close = getattr(iterator, "close", None)
        if callable(close):
            close()
    except BaseException as exc:
        cleanup_error = exc
    cancelled = await _cancel_and_drain(tasks)
    if cancelled is not None and (
        failure is None or isinstance(failure, GeneratorExit)
    ):
        raise cancelled
    if cleanup_error is not None:
        if failure is None or not isinstance(cleanup_error, Exception):
            raise cleanup_error
        failure.add_note(
            "Input iterator cleanup also raised "
            f"{type(cleanup_error).__name__}"
        )


@overload
async def gather_limited(
    awaitables: Iterable[Coroutine[Any, Any, T]],
    *,
    limit: int,
    return_exceptions: Literal[False] = False,
) -> list[T]: ...


@overload
async def gather_limited(
    awaitables: Iterable[Coroutine[Any, Any, T]],
    *,
    limit: int,
    return_exceptions: Literal[True],
) -> list[T | BaseException]: ...


@overload
async def gather_limited(
    awaitables: Iterable[Coroutine[Any, Any, T]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[T | BaseException]: ...


async def gather_limited(
    awaitables: Iterable[Coroutine[Any, Any, T]],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[T] | list[T | BaseException]:
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

    Notes
    -----
    On failure, unused coroutine objects in a sequence are closed. Lazy inputs
    are not exhausted; their iterator is closed when supported. Callers retain
    ownership of coroutine objects not yet yielded by a lazy input.
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
            if asyncio.iscoroutine(item):
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
        await _finish_coroutines(awaitables, iterator, pending, failure)
    return [ordered[index] for index in range(next_index)]


@overload
async def map_concurrent(
    func: Callable[[T], Coroutine[Any, Any, R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: Literal[False] = False,
) -> list[R]: ...


@overload
async def map_concurrent(
    func: Callable[[T], Coroutine[Any, Any, R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: Literal[True],
) -> list[R | BaseException]: ...


@overload
async def map_concurrent(
    func: Callable[[T], Coroutine[Any, Any, R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R | BaseException]: ...


async def map_concurrent(
    func: Callable[[T], Coroutine[Any, Any, R]],
    items: Iterable[T],
    *,
    limit: int,
    return_exceptions: bool = False,
) -> list[R] | list[R | BaseException]:
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
    if not callable(func):
        raise TypeError("func must be callable")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    return await gather_limited(
        (func(item) for item in items),
        limit=limit,
        return_exceptions=return_exceptions,
    )


def map_unordered(
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
    if not callable(func):
        raise TypeError("func must be callable")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    return _map_unordered_impl(func, items, limit=limit)


async def _map_unordered_impl(
    func: Callable[[T], Coroutine[Any, Any, R]],
    items: Iterable[T],
    *,
    limit: int,
) -> AsyncIterator[R]:
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
            if asyncio.iscoroutine(coroutine):
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


def _take(
    iterator: Iterator[T],
    count: int,
) -> list[T]:
    """Read a finite window without the platform-sized islice stop limit."""
    values: list[T] = []
    for _ in range(count):
        try:
            values.append(next(iterator))
        except StopIteration:
            break
    return values


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
    graceful cleanup on interruption or cancellation. Executor shutdown waits
    for already-running calls; this helper cannot forcibly interrupt a callable.

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
        If True, falls back to serial execution for callable pickling failures
        detected before any worker executes. Only PicklingError, AttributeError and
        TypeError trigger fallback; other preflight and worker/pool errors propagate.

    Returns
    -------
    list[R]
        Ordered results matching the input items.
    """
    if not callable(func):
        raise TypeError("func must be callable")
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

    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
        raise ValueError("threshold must be a non-negative integer")
    if not isinstance(fallback_serial, bool):
        raise ValueError("fallback_serial must be bool")

    item_list = list(items) if not isinstance(items, list) else items
    total = len(item_list)

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

    #? Detect unsupported callables before any worker executes. Never replay
    #? a partially executed workload after a worker or pool failure.
    if fallback_serial:
        try:
            ForkingPickler.dumps(func)
        except (PicklingError, AttributeError, TypeError):
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
    Initial lookahead consumes at most ``threshold + 1`` items, extended up to
    the detected CPU count for automatic workers. Parallel input windows contain
    at most ``2 * workers * (chunksize or 1)`` items. These are caller-configured
    budgets, not hard memory limits. Closing the iterator waits for running worker
    calls to finish; it cannot impose a deadline on an arbitrary callable.

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
        Fallback before execution for PicklingError, AttributeError or TypeError
        from multiprocessing callable encoding. Other failures propagate.

    Yields
    ------
    R
        Mapped results.
    """
    if not callable(func):
        raise TypeError("func must be callable")
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
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
        raise ValueError("threshold must be a non-negative integer")
    if not isinstance(fallback_serial, bool):
        raise ValueError("fallback_serial must be bool")

    return _process_imap_impl(
        func,
        items,
        workers=workers,
        chunksize=chunksize,
        threshold=threshold,
        fallback_serial=fallback_serial,
    )


def _process_imap_impl(
    func: Callable[[T], R],
    items: Iterable[T],
    *,
    workers: int | None = None,
    chunksize: int | None = None,
    threshold: int = 8,
    fallback_serial: bool = True,
) -> Iterator[R]:
    iterator = iter(items)
    if workers == 1:
        for item in iterator:
            yield func(item)
        return

    #? Look ahead only enough to select the serial fast path. In particular,
    #? never materialize a generator just to discover its length.
    prefix = _take(iterator, threshold + 1)
    if not prefix:
        return
    if len(prefix) <= threshold:
        for item in prefix:
            yield func(item)
        return

    max_workers = workers
    if max_workers is None:
        cpu_count = os.cpu_count() or 1
        #? Probe a CPU-sized finite window to avoid launching idle automatic
        #? workers for a short input, without exhausting a streaming source.
        if len(prefix) < cpu_count:
            prefix.extend(_take(iterator, cpu_count - len(prefix)))
        max_workers = min(cpu_count, len(prefix))
    if max_workers <= 1:
        for item in chain(prefix, iterator):
            yield func(item)
        return

    if fallback_serial:
        try:
            ForkingPickler.dumps(func)
        except (PicklingError, AttributeError, TypeError):
            for item in chain(prefix, iterator):
                yield func(item)
            return

    #? Executor.map eagerly submits the supplied iterable in some Python
    #? versions. Feed finite windows to guarantee bounded submission on all
    #? supported interpreters, preserving ordering within and across windows.
    batch_size = chunksize or 1
    window_size = max_workers * batch_size * 2
    remaining = chain(prefix, iterator)
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        while batch := _take(remaining, window_size):
            yield from executor.map(func, batch, chunksize=batch_size)


async def run_in_thread(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run a synchronous blocking callable in the default thread pool."""
    if not callable(func):
        raise TypeError("func must be callable")
    return await asyncio.to_thread(func, *args, **kwargs)


async def as_completed_limited(
    coros: Iterable[Coroutine[Any, Any, T]],
    *,
    limit: int,
) -> AsyncIterator[T]:
    """Yield results from coroutines as they finish with a concurrency ceiling.

    Parameters
    ----------
    coros : Iterable[Coroutine[Any, Any, T]]
        Coroutine sequence or lazy producer. Lazy inputs are pulled only when
        another task can be scheduled.
    limit : int
        Positive maximum number of owned tasks.

    Yields
    ------
    T
        Completed results. Ordering among simultaneous completions is unspecified.

    Notes
    -----
    Completed tasks remain owned until observed, including when another task
    fails or the consumer closes the iterator. Unused coroutine objects held by
    sequences are closed; lazy inputs follow the same ownership rules as
    ``gather_limited``. Close the async iterator explicitly when stopping early.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    iterator = iter(coros)
    pending: set[asyncio.Task[T]] = set()

    def schedule_one() -> bool:
        try:
            item = next(iterator)
        except StopIteration:
            return False
        try:
            task = asyncio.create_task(item)
        except BaseException:
            if asyncio.iscoroutine(item):
                item.close()
            raise
        pending.add(task)
        return True

    failure: BaseException | None = None
    try:
        for _ in range(limit):
            if not schedule_one():
                break
        while pending:
            done, _ = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                pending.remove(task)
                yield task.result()
                schedule_one()
    except BaseException as exc:
        failure = exc
        raise
    finally:
        await _finish_coroutines(coros, iterator, pending, failure)


class AsyncWorkerPool:
    """Bounded worker pool for asynchronous execution."""

    def __init__(self,
        limit: int = 10,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        self._limit = limit
        self._semaphore = asyncio.Semaphore(limit)
        self._tasks: set[asyncio.Task[Any]] = set()
        self._closed = False

    @property
    def limit(self) -> int:
        """Maximum number of concurrent tasks."""
        return self._limit

    @property
    def pending_count(self) -> int:
        """Number of active or pending tasks."""
        return len([t for t in self._tasks if not t.done()])

    def submit(self,
        coro_fn: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> asyncio.Task[T]:
        """Submit a coroutine function to run with concurrency control."""
        if self._closed:
            raise RuntimeError("AsyncWorkerPool is closed")
        if not callable(coro_fn):
            raise TypeError("coro_fn must be callable")

        async def _runner() -> T:
            async with self._semaphore:
                return await coro_fn(*args, **kwargs)

        task = asyncio.create_task(_runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def join(self) -> None:
        """Wait for all pending tasks in the pool to finish."""
        while self._tasks:
            pending = [t for t in self._tasks if not t.done()]
            if not pending:
                break
            await asyncio.gather(*pending, return_exceptions=True)

    async def close(self) -> None:
        """Close the pool and wait for all tasks to complete."""
        self._closed = True
        await self.join()

    async def __aenter__(self) -> AsyncWorkerPool:
        return self

    async def __aexit__(self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        await self.close()


__all__ = [
    "AsyncWorkerPool",
    "as_completed_limited",
    "gather_limited",
    "map_concurrent",
    "map_unordered",
    "process_imap",
    "process_map",
    "run_in_thread",
]
