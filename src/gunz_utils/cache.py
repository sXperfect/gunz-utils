"""Small TTL caches and asynchronous single-flight coordination."""

from __future__ import annotations

import asyncio
import functools
import threading
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Coroutine, Hashable
from dataclasses import dataclass
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


@dataclass(frozen=True)
class CacheInfo:
    """Snapshot of cache activity and capacity."""

    hits: int
    misses: int
    size: int
    maxsize: int


def _cache_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Hashable | None:
    key: Hashable = (args, tuple(sorted(kwargs.items())))
    try:
        hash(key)
    except TypeError:
        return None
    return key


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
        hits = 0
        misses = 0

        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            nonlocal hits, misses
            key = _cache_key(args, kwargs)
            if key is None:
                return func(*args, **kwargs)
            now = time.monotonic()
            with lock:
                entry = cache.get(key)
                if entry is not None and now - entry[0] <= ttl:
                    cache.move_to_end(key)
                    hits += 1
                    return entry[1]
                if entry is not None:
                    cache.pop(key, None)
                misses += 1
            value = func(*args, **kwargs)
            with lock:
                cache[key] = (time.monotonic(), value)
                cache.move_to_end(key)
                while len(cache) > maxsize:
                    cache.popitem(last=False)
            return value

        def cache_clear() -> None:
            nonlocal hits, misses
            with lock:
                cache.clear()
                hits = 0
                misses = 0

        def cache_info() -> CacheInfo:
            with lock:
                return CacheInfo(hits, misses, len(cache), maxsize)

        setattr(wrapped, "cache_clear", cache_clear)
        setattr(wrapped, "cache_info", cache_info)
        return wrapped

    return decorate


def async_ttl_cache(
    *,
    ttl: float,
    maxsize: int = 128,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Cache async results and coalesce concurrent misses for each key."""
    if ttl < 0:
        raise ValueError("ttl must be non-negative")
    if maxsize < 1:
        raise ValueError("maxsize must be at least 1")

    def decorate(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        cache: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        in_flight: dict[Hashable, asyncio.Task[T]] = {}
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            key = _cache_key(args, kwargs)
            if key is None:
                return await func(*args, **kwargs)
            async with lock:
                now = time.monotonic()
                entry = cache.get(key)
                if entry is not None and now - entry[0] <= ttl:
                    cache.move_to_end(key)
                    return entry[1]
                if entry is not None:
                    cache.pop(key, None)
                task = in_flight.get(key)
                if task is None:
                    task = asyncio.create_task(func(*args, **kwargs))
                    in_flight[key] = task
            try:
                value = await asyncio.shield(task)
            finally:
                if task.done():
                    async with lock:
                        if in_flight.get(key) is task:
                            in_flight.pop(key, None)
            async with lock:
                cache[key] = (time.monotonic(), value)
                cache.move_to_end(key)
                while len(cache) > maxsize:
                    cache.popitem(last=False)
            return value

        async def cache_clear() -> None:
            async with lock:
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


__all__ = ["CacheInfo", "SingleFlight", "async_ttl_cache", "ttl_cache"]
