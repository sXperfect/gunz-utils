"""Small TTL caches and asynchronous single-flight coordination."""

from __future__ import annotations

import asyncio
import functools
import threading
import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
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


__all__ = [
    "CacheInfo",
    "RecencyTTLPolicy",
    "SingleFlight",
    "async_ttl_cache",
    "ttl_cache",
]



@dataclass(frozen=True, slots=True)
class RecencyTTLPolicy:
    """Choose cache TTL from the age of source data.

    Parameters
    ----------
    recent_window : timedelta
        Data age considered recent.
    recent_ttl : timedelta
        TTL for recent non-empty data.
    historical_ttl : timedelta
        TTL for data older than recent_window.
    empty_recent_ttl : timedelta | None, optional
        Optional shorter/different TTL for empty recent responses. When None,
        recent_ttl is used.

    Notes
    -----
    This policy knows nothing about markets, crawlers, providers, or datasets.
    Consumers define what timestamp represents the data's freshness boundary.
    """

    recent_window: timedelta
    recent_ttl: timedelta
    historical_ttl: timedelta
    empty_recent_ttl: timedelta | None = None

    def __post_init__(self) -> None:
        """Validate non-negative windows and TTLs."""
        values = {
            "recent_window": self.recent_window,
            "recent_ttl": self.recent_ttl,
            "historical_ttl": self.historical_ttl,
        }
        if self.empty_recent_ttl is not None:
            values["empty_recent_ttl"] = self.empty_recent_ttl

        for name, value in values.items():
            if not isinstance(value, timedelta):
                raise TypeError(f"{name} must be datetime.timedelta")
            if value < timedelta(0):
                raise ValueError(f"{name} must be non-negative")

    def ttl_for(
        self,
        observed_at: datetime,
        *,
        empty: bool = False,
        now: datetime | None = None,
    ) -> timedelta:
        """Return the TTL appropriate for one source timestamp.

        Parameters
        ----------
        observed_at : datetime
            Time represented by the cached source data. Must be timezone-aware.
        empty : bool, optional
            Whether the source result is empty.
        now : datetime | None, optional
            Reference time for deterministic tests. Defaults to current UTC.

        Returns
        -------
        timedelta
            Selected TTL.

        Raises
        ------
        ValueError
            If observed_at or now is timezone-naive.
        """
        if not isinstance(observed_at, datetime):
            raise TypeError("observed_at must be datetime")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        reference = now or datetime.now(UTC)
        if not isinstance(reference, datetime):
            raise TypeError("now must be datetime or None")
        if reference.tzinfo is None or reference.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        age = reference.astimezone(UTC) - observed_at.astimezone(UTC)
        recent = age <= self.recent_window
        if recent:
            if empty and self.empty_recent_ttl is not None:
                return self.empty_recent_ttl
            return self.recent_ttl
        return self.historical_ttl
