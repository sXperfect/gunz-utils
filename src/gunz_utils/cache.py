"""Small TTL caches and asynchronous single-flight coordination."""

from __future__ import annotations

import asyncio
import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Coroutine, Hashable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


def ttl_cache(
    *,
    ttl: float,
    maxsize: int = 128,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Cache synchronous function results for a bounded amount of time."""
    if ttl < 0:
        raise ValueError("ttl must be non-negative")
    if maxsize < 1:
        raise ValueError("maxsize must be at least 1")

    def decorate(func: Callable[P, T]) -> Callable[P, T]:
        cache: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            key: Hashable = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                entry = cache.get(key)
                if entry is not None and now - entry[0] <= ttl:
                    cache.move_to_end(key)
                    return entry[1]
                if entry is not None:
                    cache.pop(key, None)
            value = func(*args, **kwargs)
            with lock:
                cache[key] = (time.monotonic(), value)
                cache.move_to_end(key)
                while len(cache) > maxsize:
                    cache.popitem(last=False)
            return value

        def cache_clear() -> None:
            with lock:
                cache.clear()

        setattr(wrapped, "cache_clear", cache_clear)
        return wrapped

    return decorate


class SingleFlight:
    """Coalesce concurrent async work sharing the same key."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[Hashable, asyncio.Task[Any]] = {}

    async def run(
        self,
        key: Hashable,
        factory: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Run one factory per key and share its result with concurrent callers."""
        async with self._lock:
            task = self._tasks.get(key)
            if task is None:
                task = asyncio.create_task(factory())
                self._tasks[key] = task
        try:
            return await asyncio.shield(task)
        finally:
            if task.done():
                async with self._lock:
                    if self._tasks.get(key) is task:
                        self._tasks.pop(key, None)


__all__ = ["SingleFlight", "ttl_cache"]
