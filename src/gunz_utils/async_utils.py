"""Async lifecycle and cancellation helpers."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio
import contextlib
import functools
import inspect
import math
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

T = TypeVar("T")


async def cancel_and_wait(
    *tasks: asyncio.Future[object] | asyncio.Task[object],
) -> None:
    """Cancel tasks and wait for their cleanup without leaking cancellation.

    Parameters
    ----------
    tasks : asyncio.Future[object] | asyncio.Task[object]
        Futures or tasks to cancel and await.
    """
    for task in tasks:
        if not isinstance(task, (asyncio.Future, asyncio.Task)):
            raise TypeError(
                f"expected asyncio.Task or asyncio.Future, got {type(task).__name__}"
            )
        task.cancel()
    if tasks:
        drain = asyncio.gather(*tasks, return_exceptions=True)
        cancelled: asyncio.CancelledError | None = None
        while not drain.done():
            try:
                await asyncio.shield(drain)
            except asyncio.CancelledError as exc:
                cancelled = exc
        if cancelled is not None:
            raise cancelled


async def with_timeout(
    awaitable: Awaitable[T],
    timeout: float | None,
) -> T:
    """Await work with an optional timeout using asyncio.timeout.

    Parameters
    ----------
    awaitable : Awaitable[T]
        awaitable parameter.
    timeout : float | None
        timeout parameter.

    Returns
    -------
    T
        The result of the operation.
    """
    if timeout is None:
        return await awaitable
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        if inspect.iscoroutine(awaitable):
            awaitable.close()
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    async with asyncio.timeout(float(timeout)):
        return await awaitable


async def gather_with_concurrency(
    max_concurrency: int,
    *awaitables: Awaitable[T],
) -> list[T]:
    """Execute awaitables with bounded parallelism using an asyncio Semaphore."""
    if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int) or max_concurrency < 1:
        raise ValueError("max_concurrency must be an integer >= 1")

    sem = asyncio.Semaphore(max_concurrency)

    async def _sem_task(
        coro: Awaitable[T],
    ) -> T:
        async with sem:
            return await coro

    return await asyncio.gather(*(_sem_task(a) for a in awaitables))


@asynccontextmanager
async def async_timeout(
    seconds: float,
) -> AsyncIterator[None]:
    """Async context manager applying a deadline using asyncio.timeout."""
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
        raise ValueError("seconds must be a non-negative number")
    async with asyncio.timeout(float(seconds)):
        yield


def async_retry(
    retries: int = 3,
    delay: float = 0.05,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Async decorator that retries failing coroutines with exponential backoff."""
    if retries < 0:
        raise ValueError("retries must be non-negative")

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> T:
            current_delay = delay
            last_exc: Exception | None = None
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == retries:
                        raise
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            if last_exc is not None:
                raise last_exc
            raise RuntimeError("unreachable retry state")
        return wrapper
    return decorator


def async_throttle(
    seconds: float,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Async decorator restricting call rate to at most once per `seconds`."""
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    def decorator(
        func: Callable[..., Awaitable[T]],
    ) -> Callable[..., Awaitable[T]]:
        last_called = 0.0
        lock = asyncio.Lock()
        last_result: Any = None

        @functools.wraps(func)
        async def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> T:
            nonlocal last_called, last_result
            async with lock:
                now = time.monotonic()
                if now - last_called >= seconds:
                    last_called = now
                    last_result = await func(*args, **kwargs)
                return last_result
        return wrapper
    return decorator


def async_debounce(
    seconds: float,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Async decorator delaying coroutine execution until `seconds` elapsed since last call."""
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Awaitable[Any]]:
        task: asyncio.Task[Any] | None = None

        @functools.wraps(func)
        async def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> None:
            nonlocal task
            if task is not None and not task.done():
                task.cancel()

            async def _delayed() -> None:
                await asyncio.sleep(seconds)
                await func(*args, **kwargs)

            task = asyncio.create_task(_delayed())

        return wrapper
    return decorator


async def run_in_executor(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run a blocking synchronous callable in the default thread pool executor."""
    loop = asyncio.get_running_loop()
    p_func = functools.partial(func, *args, **kwargs) if kwargs else func
    if kwargs:
        return await loop.run_in_executor(None, p_func)
    return await loop.run_in_executor(None, p_func, *args)


async def async_first_completed(
    *awaitables: Awaitable[T],
) -> T:
    """Return the result of the first awaitable to finish and cancel the rest."""
    if not awaitables:
        raise ValueError("at least one awaitable must be provided")

    tasks = [asyncio.ensure_future(a) for a in awaitables]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for p in pending:
        p.cancel()

    #? Collect result or exception from completed task
    first = next(iter(done))
    return first.result()


class AsyncBarrier:
    """Async synchronization barrier coordinating a fixed number of tasks."""

    def __init__(self,
        parties: int,
    ) -> None:
        if parties < 1:
            raise ValueError("parties must be >= 1")
        self.parties = parties
        self._count = 0
        self._event = asyncio.Event()

    async def wait(self) -> int:
        """Wait for all parties to arrive at the barrier."""
        index = self._count
        self._count += 1
        if self._count == self.parties:
            self._event.set()
            return index
        await self._event.wait()
        return index

    def reset(self) -> None:
        """Reset barrier for another cycle."""
        self._count = 0
        self._event.clear()


class AsyncPeriodicTask:
    """Background recurring task running a coroutine on an interval."""

    def __init__(self,
        func: Callable[[], Awaitable[Any]],
        interval: float,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval must be positive")
        self.func = func
        self.interval = interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start the periodic task in the background."""
        if self._running:
            return
        self._running = True

        async def _loop() -> None:
            while self._running:
                with contextlib.suppress(Exception):
                    await self.func()
                try:
                    await asyncio.sleep(self.interval)
                except asyncio.CancelledError:
                    break

        self._task = asyncio.create_task(_loop())

    def stop(self) -> None:
        """Stop the periodic task."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()


__all__ = [
    "AsyncBarrier",
    "AsyncPeriodicTask",
    "async_debounce",
    "async_first_completed",
    "async_retry",
    "async_throttle",
    "async_timeout",
    "cancel_and_wait",
    "gather_with_concurrency",
    "run_in_executor",
    "with_timeout",
]
