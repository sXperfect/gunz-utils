"""Small TTL caches and asynchronous single-flight coordination."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
# isort: split

from __future__ import annotations

import asyncio
import functools
import math
import threading
import time
import types
from collections import OrderedDict
from collections.abc import Callable, Coroutine, Hashable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Generic, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CacheInfo:
    """Snapshot of cache activity and capacity."""

    hits: int
    misses: int
    size: int
    maxsize: int

    @property
    def hit_rate(self) -> float:
        """Return the fraction of successful cache lookups (0.0 to 1.0).

        Returns 0.0 when no lookups (hits + misses) have been performed.
        """
        total = self.hits + self.misses
        return 0.0 if total == 0 else self.hits / total


_KW_SENTINEL: object = object()


def _cache_key(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Hashable | None:
    """Compute a hashable cache key from arguments.

    Includes a zero-allocation fast path for positional-only calls.

    Parameters
    ----------
    args : tuple[Any, ...]
        args parameter.
    kwargs : dict[str, Any]
        kwargs parameter.

    Returns
    -------
    Hashable | None
        The result of the operation.
    """
    if not kwargs:
        key: Hashable = args
    else:
        key = (args, _KW_SENTINEL, tuple(sorted(kwargs.items())))
    try:
        hash(key)
    except TypeError:
        return None
    return key


def _validate_cache_bounds(
    *,
    ttl: float,
    maxsize: int,
) -> None:
    """_validate_cache_bounds() function.

    Parameters
    ----------
    ttl : float
        ttl parameter.
    maxsize : int
        maxsize parameter.
    """
    if (
        isinstance(ttl, bool)
        or not isinstance(ttl, (int, float))
        or not math.isfinite(float(ttl))
        or ttl < 0
    ):
        raise ValueError("ttl must be a finite non-negative number")
    if isinstance(maxsize, bool) or not isinstance(maxsize, int) or maxsize < 1:
        raise ValueError("maxsize must be a positive integer")


def _validate_callable_target(
    func: Any,
) -> None:
    if isinstance(func, (staticmethod, classmethod)):
        if not callable(func.__func__):
            raise TypeError("func must be callable")
    elif not callable(func):
        raise TypeError("func must be callable")


class _TTLCache(Generic[P, T]):
    """Decorated callable with a bounded, time-based cache.

    Attributes
    ----------
    cache_clear : Callable[[], None]
        Drop all cached entries and reset hit/miss counters.
    cache_info : Callable[[], CacheInfo]
        Return a snapshot of cache activity and capacity.
    cache_invalidate : Callable[..., bool]
        Evict a single cache entry for given arguments.

    The class carries the cache bookkeeping so the returned object can expose
    ``cache_clear``/``cache_info`` as first-class, type-checked attributes (a
    plain function cannot declare them without ``setattr`` or a cast).
    """

    def __init__(self,
        func: Callable[P, T],
        *,
        ttl: float,
        maxsize: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        functools.update_wrapper(self, func)
        self._func = func
        self._ttl = ttl
        self._maxsize = maxsize
        self._clock = clock if clock is not None else time.monotonic
        self._cache: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._generation = 0

    def __get__(self,
        instance: Any,
        owner: Any = None,
    ) -> Any:
        if isinstance(self._func, staticmethod):
            return self
        if isinstance(self._func, classmethod):
            target = owner if owner is not None else type(instance)
            return types.MethodType(self, target)
        if instance is None:
            return self
        return types.MethodType(self, instance)

    def __call__(self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        func = self._func
        if isinstance(func, (staticmethod, classmethod)):
            func = func.__func__
        key = _cache_key(args, kwargs)
        if key is None:
            return func(*args, **kwargs)
        now = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] <= self._ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return entry[1]
            if entry is not None:
                self._cache.pop(key, None)
            self._misses += 1
            generation = self._generation
        value = func(*args, **kwargs)
        with self._lock:
            if generation == self._generation:
                now_write = self._clock()
                self._cache[key] = (now_write, value)
                self._cache.move_to_end(key)
                if len(self._cache) > self._maxsize:
                    for k in list(self._cache.keys()):
                        if now_write - self._cache[k][0] > self._ttl:
                            self._cache.pop(k, None)
                            if len(self._cache) <= self._maxsize:
                                break
                while len(self._cache) > self._maxsize:
                    self._cache.popitem(last=False)
        return value

    def cache_clear(self) -> None:
        """Drop all cached entries and reset the hit/miss counters.

        No parameters and no return value.
        """
        with self._lock:
            self._generation += 1
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def cache_invalidate(self,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Evict the cached entry for given arguments.

        Returns True if a valid (non-expired) entry was removed, False otherwise.
        """
        key = _cache_key(args, kwargs)
        if key is None:
            return False
        now = self._clock()
        with self._lock:
            entry = self._cache.pop(key, None)
            if entry is not None:
                return (now - entry[0]) <= self._ttl
            return False

    def cache_info(self) -> CacheInfo:
        """Return a snapshot of cache activity and capacity.

        Returns
        -------
        CacheInfo
            The result of the operation.
        """
        with self._lock:
            return CacheInfo(
                self._hits, self._misses, len(self._cache), self._maxsize
            )


def ttl_cache(
    *,
    ttl: float,
    maxsize: int = 128,
    clock: Callable[[], float] | None = None,
) -> Callable[[Callable[P, T]], _TTLCache[P, T]]:
    """Cache synchronous function results for a bounded amount of time.

    Cache bookkeeping is protected by a lock; user functions run outside it.
    Concurrent misses for one key may compute independently. Clearing invalidates
    results from computations already running: their callers retain their own
    result, but those computations cannot repopulate the cleared cache.

    Parameters
    ----------
    ttl : float
        ttl parameter.
    maxsize : int
        maxsize parameter.
    clock : Callable[[], float] | None, optional
        Clock returning monotonic seconds. Defaults to time.monotonic.

    Returns
    -------
    Callable[[Callable[P, T]], _TTLCache[P, T]]
        The result of the operation.
    """
    _validate_cache_bounds(ttl=ttl, maxsize=maxsize)
    if clock is not None and not callable(clock):
        raise TypeError("clock must be callable or None")

    def decorate(
        func: Callable[P, T],
    ) -> _TTLCache[P, T]:
        """decorate() function.

        Parameters
        ----------
        func : Callable[P, T]
            func parameter.

        Returns
        -------
        _TTLCache[P, T]
            The result of the operation.
        """
        _validate_callable_target(func)
        return _TTLCache(func, ttl=ttl, maxsize=maxsize, clock=clock)

    return decorate


class _AsyncTTLCache(Generic[P, T]):
    """Decorated async callable caching results and coalescing concurrent misses.

    Attributes
    ----------
    cache_clear : Callable[[], Awaitable[None]]
        Drop all cached entries (awaitable, matching the async API).
    cache_info : Callable[[], CacheInfo]
        Return a snapshot of cache activity and capacity.
    cache_invalidate : Callable[..., Awaitable[bool]]
        Evict a single cache entry for given arguments.

    Carries the async cache/in-flight bookkeeping so ``cache_clear`` is a
    type-checked attribute without ``setattr`` or a cast. Concurrent calls and
    pending producers must share one event loop; cross-thread independent loops
    cannot await the same in-flight Task. Cancelling a waiter leaves its shared
    producer running; ``cache_clear`` detaches old producers without cancelling
    existing waiters.
    """

    def __init__(self,
        func: Callable[P, Coroutine[Any, Any, T]],
        *,
        ttl: float,
        maxsize: int,
        clock: Callable[[], float] | None = None,
    ) -> None:
        functools.update_wrapper(self, func)
        self._func = func
        self._ttl = ttl
        self._maxsize = maxsize
        self._clock = clock if clock is not None else time.monotonic
        self._cache: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()
        self._in_flight: dict[Hashable, asyncio.Task[T]] = {}
        self._hits = 0
        self._misses = 0
        self._generation = 0
        self._lock = asyncio.Lock()

    def __get__(self,
        instance: Any,
        owner: Any = None,
    ) -> Any:
        if isinstance(self._func, staticmethod):
            return self
        if isinstance(self._func, classmethod):
            target = owner if owner is not None else type(instance)
            return types.MethodType(self, target)
        if instance is None:
            return self
        return types.MethodType(self, instance)

    async def __call__(self,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        func = self._func
        if isinstance(func, (staticmethod, classmethod)):
            func = func.__func__
        key = _cache_key(args, kwargs)
        if key is None:
            return await func(*args, **kwargs)
        async with self._lock:
            now = self._clock()
            entry = self._cache.get(key)
            if entry is not None and now - entry[0] <= self._ttl:
                self._cache.move_to_end(key)
                self._hits += 1
                return entry[1]
            if entry is not None:
                self._cache.pop(key, None)
            self._misses += 1
            task = self._in_flight.get(key)
            if task is None:
                generation = self._generation

                async def _producer() -> T:
                    """_producer() function.

                    Returns
                    -------
                    T
                        The result of the operation.
                    """
                    try:
                        val = await func(*args, **kwargs)
                        async with self._lock:
                            if generation != self._generation:
                                return val
                            now_write = self._clock()
                            self._cache[key] = (now_write, val)
                            self._cache.move_to_end(key)
                            if len(self._cache) > self._maxsize:
                                for k in list(self._cache.keys()):
                                    if now_write - self._cache[k][0] > self._ttl:
                                        self._cache.pop(k, None)
                                        if len(self._cache) <= self._maxsize:
                                            break
                            while len(self._cache) > self._maxsize:
                                self._cache.popitem(last=False)
                        return val
                    finally:
                        async with self._lock:
                            if self._in_flight.get(key) is current_task:
                                self._in_flight.pop(key, None)

                coroutine = _producer()
                try:
                    current_task = asyncio.create_task(coroutine)
                except BaseException:
                    coroutine.close()
                    raise

                def _silence_unretrieved(
                    t: asyncio.Task[Any],
                ) -> None:
                    """_silence_unretrieved() function.

                    Parameters
                    ----------
                    t : asyncio.Task[Any]
                        t parameter.
                    """
                    if not t.cancelled():
                        t.exception()

                current_task.add_done_callback(_silence_unretrieved)
                self._in_flight[key] = current_task
                task = current_task

        return await asyncio.shield(task)

    async def cache_clear(self) -> None:
        """Drop all cached entries (awaitable, matching the async API).

        No parameters and no return value.
        """
        async with self._lock:
            self._generation += 1
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            #? Detach old producers without cancelling callers already awaiting
            #? them. A subsequent lookup starts a fresh generation.
            self._in_flight.clear()

    async def cache_invalidate(self,
        *args: Any,
        **kwargs: Any,
    ) -> bool:
        """Evict the cached entry for given arguments.

        Returns True if a valid (non-expired) entry was removed, False otherwise.
        """
        key = _cache_key(args, kwargs)
        if key is None:
            return False
        now = self._clock()
        async with self._lock:
            entry = self._cache.pop(key, None)
            if entry is not None:
                return (now - entry[0]) <= self._ttl
            return False

    def cache_info(self) -> CacheInfo:
        """Return a snapshot of cache activity and capacity.

        Returns
        -------
        CacheInfo
            The result of the operation.
        """
        return CacheInfo(
            self._hits, self._misses, len(self._cache), self._maxsize
        )


def async_ttl_cache(
    *,
    ttl: float,
    maxsize: int = 128,
    clock: Callable[[], float] | None = None,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, T]]], _AsyncTTLCache[P, T]
]:
    """Cache async results and coalesce concurrent misses for each key.

    Concurrent calls with pending producers must share one event loop. Cancelling
    a waiter leaves its shared producer running. Awaiting ``cache_clear`` detaches
    old producers without cancelling their existing waiters; old results cannot
    populate the fresh cache generation.

    Parameters
    ----------
    ttl : float
        ttl parameter.
    maxsize : int
        maxsize parameter.
    clock : Callable[[], float] | None, optional
        Clock returning monotonic seconds. Defaults to time.monotonic.

    Returns
    -------
    Callable[[Callable[P, Coroutine[Any, Any, T]]], _AsyncTTLCache[P, T]]
        The result of the operation.
    """
    _validate_cache_bounds(ttl=ttl, maxsize=maxsize)
    if clock is not None and not callable(clock):
        raise TypeError("clock must be callable or None")

    def decorate(
        func: Callable[P, Coroutine[Any, Any, T]],
    ) -> _AsyncTTLCache[P, T]:
        """decorate() function.

        Parameters
        ----------
        func : Callable[P, Coroutine[Any, Any, T]]
            func parameter.

        Returns
        -------
        _AsyncTTLCache[P, T]
            The result of the operation.
        """
        _validate_callable_target(func)
        return _AsyncTTLCache(func, ttl=ttl, maxsize=maxsize, clock=clock)

    return decorate


class SingleFlight:
    """Coalesce concurrent async work sharing the same key.

    Concurrent calls with pending work must share one event loop. A Task owned
    by another live thread's loop cannot be awaited here. Cancelling a waiter
    leaves the shared producer running for other callers.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[Hashable, asyncio.Task[Any]] = {}

    @property
    def in_flight_count(self) -> int:
        """Return the number of in-flight tasks currently being tracked."""
        return len(self._tasks)

    def is_in_flight(self,
        key: Hashable,
    ) -> bool:
        """Return whether a task for key is currently in-flight."""
        try:
            hash(key)
        except TypeError as exc:
            raise TypeError(f"key must be hashable, got {type(key).__name__}") from exc
        return key in self._tasks

    async def run(self,
        key: Hashable,
        factory: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Run one factory per key and share its result with concurrent callers.

        Parameters
        ----------
        key : Hashable
            key parameter.
        factory : Callable[[], Coroutine[Any, Any, T]]
            factory parameter.

        Returns
        -------
        T
            The result of the operation.
        """
        if not callable(factory):
            raise TypeError("factory must be callable")
        try:
            hash(key)
        except TypeError as exc:
            raise TypeError(f"key must be hashable, got {type(key).__name__}") from exc

        async with self._lock:
            task = self._tasks.get(key)
            if task is None:
                async def _worker() -> T:
                    """_worker() function.

                    Returns
                    -------
                    T
                        The result of the operation.
                    """
                    try:
                        return await factory()
                    finally:
                        async with self._lock:
                            if self._tasks.get(key) is current_task:
                                self._tasks.pop(key, None)

                coroutine = _worker()
                try:
                    current_task = asyncio.create_task(coroutine)
                except BaseException:
                    coroutine.close()
                    raise

                def _silence(
                    t: asyncio.Task[Any],
                ) -> None:
                    """_silence() function.

                    Parameters
                    ----------
                    t : asyncio.Task[Any]
                        t parameter.
                    """
                    if not t.cancelled():
                        t.exception()

                current_task.add_done_callback(_silence)
                self._tasks[key] = current_task
                task = current_task

        return await asyncio.shield(task)


@dataclass(slots=True)
class CacheMetrics:
    """Tracks cache hits, misses, and evictions."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """Return the fraction of successful cache lookups (0.0 to 1.0)."""
        total = self.hits + self.misses
        return 0.0 if total == 0 else self.hits / total

    def record_hit(self) -> None:
        self.hits += 1

    def record_miss(self) -> None:
        self.misses += 1

    def record_eviction(self) -> None:
        self.evictions += 1

    def reset(self) -> None:
        self.hits = 0
        self.misses = 0
        self.evictions = 0


class FIFOCache(Generic[T]):
    """First-In First-Out cache bounded by capacity."""

    def __init__(self,
        capacity: int,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be an integer >= 1")
        self.capacity = capacity
        self._cache: OrderedDict[Any, T] = OrderedDict()
        self.metrics = CacheMetrics()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self,
        key: Any,
    ) -> bool:
        return key in self._cache

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.metrics.reset()

    def get(self,
        key: Any,
        default: Any = None,
    ) -> Any:
        with self._lock:
            if key in self._cache:
                self.metrics.record_hit()
                return self._cache[key]
            self.metrics.record_miss()
            return default

    def put(self,
        key: Any,
        value: T,
    ) -> None:
        with self._lock:
            if key in self._cache:
                self._cache[key] = value
                return
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
                self.metrics.record_eviction()
            self._cache[key] = value

    def __getitem__(self,
        key: Any,
    ) -> T:
        res = self.get(key, default=_KW_SENTINEL)
        if res is _KW_SENTINEL:
            raise KeyError(key)
        return res

    def __setitem__(self,
        key: Any,
        value: T,
    ) -> None:
        self.put(key, value)


class LFUCache(Generic[T]):
    """Least-Frequently Used cache with O(1) frequency bucket updates."""

    def __init__(self,
        capacity: int,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be an integer >= 1")
        self.capacity = capacity
        self._key_val: dict[Any, T] = {}
        self._key_freq: dict[Any, int] = {}
        self._freq_keys: dict[int, OrderedDict[Any, None]] = {}
        self._min_freq: int = 0
        self.metrics = CacheMetrics()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._key_val)

    def __contains__(self,
        key: Any,
    ) -> bool:
        return key in self._key_val

    def clear(self) -> None:
        with self._lock:
            self._key_val.clear()
            self._key_freq.clear()
            self._freq_keys.clear()
            self._min_freq = 0
            self.metrics.reset()

    def _touch(self,
        key: Any,
    ) -> None:
        freq = self._key_freq[key]
        del self._freq_keys[freq][key]
        if not self._freq_keys[freq]:
            del self._freq_keys[freq]
            if self._min_freq == freq:
                self._min_freq += 1
        new_freq = freq + 1
        self._key_freq[key] = new_freq
        if new_freq not in self._freq_keys:
            self._freq_keys[new_freq] = OrderedDict()
        self._freq_keys[new_freq][key] = None

    def get(self,
        key: Any,
        default: Any = None,
    ) -> Any:
        with self._lock:
            if key in self._key_val:
                self.metrics.record_hit()
                self._touch(key)
                return self._key_val[key]
            self.metrics.record_miss()
            return default

    def put(self,
        key: Any,
        value: T,
    ) -> None:
        with self._lock:
            if key in self._key_val:
                self._key_val[key] = value
                self._touch(key)
                return
            if len(self._key_val) >= self.capacity:
                #? Evict least frequently used key (earliest inserted in min_freq bucket)
                evict_bucket = self._freq_keys[self._min_freq]
                evict_key, _ = evict_bucket.popitem(last=False)
                if not evict_bucket:
                    del self._freq_keys[self._min_freq]
                del self._key_val[evict_key]
                del self._key_freq[evict_key]
                self.metrics.record_eviction()

            self._key_val[key] = value
            self._key_freq[key] = 1
            self._min_freq = 1
            if 1 not in self._freq_keys:
                self._freq_keys[1] = OrderedDict()
            self._freq_keys[1][key] = None

    def __getitem__(self,
        key: Any,
    ) -> T:
        res = self.get(key, default=_KW_SENTINEL)
        if res is _KW_SENTINEL:
            raise KeyError(key)
        return res

    def __setitem__(self,
        key: Any,
        value: T,
    ) -> None:
        self.put(key, value)


class TTLCache(Generic[T]):
    """Time-To-Live bounded cache with automatic expiration."""

    def __init__(self,
        capacity: int,
        ttl_seconds: float,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be an integer >= 1")
        if (
            isinstance(ttl_seconds, bool)
            or not isinstance(ttl_seconds, (int, float))
            or ttl_seconds <= 0
        ):
            raise ValueError("ttl_seconds must be a positive number")
        self.capacity = capacity
        self.ttl_seconds = float(ttl_seconds)
        self._cache: OrderedDict[Any, tuple[T, float]] = OrderedDict()
        self.metrics = CacheMetrics()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        self._purge_expired()
        return len(self._cache)

    def __contains__(self,
        key: Any,
    ) -> bool:
        self._purge_expired()
        return key in self._cache

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.metrics.reset()

    def _purge_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp) in self._cache.items() if exp <= now]
            for k in expired:
                del self._cache[k]
                self.metrics.record_eviction()

    def get(self,
        key: Any,
        default: Any = None,
    ) -> Any:
        now = time.monotonic()
        with self._lock:
            if key in self._cache:
                val, exp = self._cache[key]
                if exp > now:
                    self.metrics.record_hit()
                    return val
                del self._cache[key]
                self.metrics.record_eviction()
            self.metrics.record_miss()
            return default

    def put(self,
        key: Any,
        value: T,
    ) -> None:
        now = time.monotonic()
        exp = now + self.ttl_seconds
        with self._lock:
            if key in self._cache:
                self._cache[key] = (value, exp)
                return
            #? Purge expired inline
            expired = [k for k, (_, e) in self._cache.items() if e <= now]
            for k in expired:
                del self._cache[k]
                self.metrics.record_eviction()
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
                self.metrics.record_eviction()
            self._cache[key] = (value, exp)

    def __getitem__(self,
        key: Any,
    ) -> T:
        res = self.get(key, default=_KW_SENTINEL)
        if res is _KW_SENTINEL:
            raise KeyError(key)
        return res

    def __setitem__(self,
        key: Any,
        value: T,
    ) -> None:
        self.put(key, value)


def memoize_ttl(
    ttl_seconds: float,
    maxsize: int = 128,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Memoize a function's return values with TTL expiration and max capacity."""
    return ttl_cache(ttl=ttl_seconds, maxsize=maxsize)


__all__ = [
    "CacheInfo",
    "CacheMetrics",
    "FIFOCache",
    "LFUCache",
    "RecencyTTLPolicy",
    "SingleFlight",
    "TTLCache",
    "async_ttl_cache",
    "memoize_ttl",
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

    def ttl_for(self,
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
        if not isinstance(empty, bool):
            raise TypeError("empty must be bool")
        if not isinstance(observed_at, datetime):
            raise TypeError("observed_at must be datetime")
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")

        reference = datetime.now(UTC) if now is None else now
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

    def ttl_seconds_for(self,
        observed_at: datetime,
        *,
        empty: bool = False,
        now: datetime | None = None,
    ) -> float:
        """Return the TTL in seconds appropriate for one source timestamp.

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
        float
            Selected TTL in seconds.
        """
        return self.ttl_for(observed_at, empty=empty, now=now).total_seconds()
