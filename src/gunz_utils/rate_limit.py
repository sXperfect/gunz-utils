"""Async token-bucket rate limiting."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import math
import sys
import threading
import time
from collections.abc import Callable
from typing import Any


class RateLimitExceeded(RuntimeError):
    """Raised when an operation exceeds its configured rate limit."""

    def __init__(self,
        message: str = "Rate limit exceeded",
        retry_after: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AsyncRateLimiter:
    """Token-bucket limiter with bounded burst capacity."""

    def __init__(self,
        rate: float,
        *,
        capacity: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._clock: Callable[[], float] = (
            clock if clock is not None else (lambda: time.monotonic())
        )
        self.rate = self._finite_positive(rate, name="rate")
        raw_capacity = max(1.0, self.rate) if capacity is None else capacity
        self.capacity = self._finite_positive(raw_capacity, name="capacity")
        self._tokens = self.capacity
        self._updated = self._clock()
        self._lock = asyncio.Lock()

    @property
    def available_tokens(self) -> float:
        """Return the estimated token balance without waiting.

        Returns
        -------
        float
            The result of the operation.
        """
        elapsed = max(0.0, self._clock() - self._updated)
        try:
            tokens = self._tokens + elapsed * self.rate
        except OverflowError:
            tokens = self.capacity
        return min(self.capacity, tokens)

    #? GS046 false positive: 'tokens' parameter is token-bucket capacity,
    #? not an authentication credential or secret token.
    async def try_acquire(self,  # gunz-style: ignore[GS046]
        tokens: float = 1.0,
    ) -> bool:
        """Consume tokens immediately when available without waiting.

        Parameters
        ----------
        tokens : float
            tokens parameter.

        Returns
        -------
        bool
            The result of the operation.
        """
        tokens = self._validate_tokens(tokens)
        async with self._lock:
            self._refill()
            if self._tokens < tokens:
                return False
            self._tokens -= tokens
            return True

    #? GS046 false positive: 'tokens' parameter is token-bucket capacity,
    #? not an authentication credential or secret token.
    async def acquire(self,  # gunz-style: ignore[GS046]
        tokens: float = 1.0,
        *,
        timeout: float | None = None,
    ) -> None:
        """Wait until tokens are available or the optional timeout expires.

        Parameters
        ----------
        tokens : float
            tokens parameter.
        timeout : float | None
            timeout parameter.
        """
        tokens = self._validate_tokens(tokens)
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 <= timeout <= sys.float_info.max
        ):
            raise ValueError("timeout must be a finite non-negative number or None")
        if timeout is not None:
            try:
                deadline = self._clock() + timeout
            except OverflowError as error:
                raise OverflowError(
                    "timeout deadline calculation overflowed") from error
            if not math.isfinite(deadline):
                raise OverflowError("timeout deadline calculation overflowed")
        else:
            deadline = None
        first_attempt = True
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    if (
                        not first_attempt
                        and deadline is not None
                        and self._clock() > deadline
                    ):
                        raise TimeoutError("rate-limit acquisition timed out")
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                try:
                    wait = deficit / self.rate
                except OverflowError:
                    wait = float("inf")
            first_attempt = False
            if deadline is not None:
                budget = deadline - self._clock()
                if budget <= 0 or wait > budget or not math.isfinite(wait):
                    raise TimeoutError("rate-limit acquisition timed out")
            elif not math.isfinite(wait):
                raise OverflowError(
                    "calculated rate-limit wait duration is non-finite"
                )
            await asyncio.sleep(wait)

    @staticmethod
    def _finite_positive(
        value: float,
        *,
        name: str,
    ) -> float:
        """_finite_positive() function.

        Parameters
        ----------
        value : float
            value parameter.
        name : str
            name parameter.

        Returns
        -------
        float
            The result of the operation.
        """
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 < value <= sys.float_info.max
        ):
            raise ValueError(f"{name} must be a finite positive number")
        return float(value)

    def _validate_tokens(self,
        tokens: float,
    ) -> float:
        """_validate_tokens() function.

        Parameters
        ----------
        tokens : float
            tokens parameter.

        Returns
        -------
        float
            The result of the operation.
        """
        value = self._finite_positive(tokens, name="tokens")
        #? Check the original value before rounding a large integer to float.
        if tokens > self.capacity:
            raise ValueError("tokens must be positive and <= capacity")
        return value

    def _refill(self) -> None:
        """_refill() function.

        No parameters and no return value.
        """
        now = self._clock()
        elapsed = max(0.0, now - self._updated)
        try:
            tokens = self._tokens + elapsed * self.rate
        except OverflowError:
            tokens = self.capacity
        self._tokens = min(self.capacity, tokens)
        self._updated = now

    async def reset(self) -> None:
        """Reset the token bucket to full capacity."""
        async with self._lock:
            self._tokens = self.capacity
            self._updated = self._clock()

    async def __aenter__(self) -> AsyncRateLimiter:
        await self.acquire()
        return self

    async def __aexit__(self,
        *args: object,
    ) -> None:
        return None


class RateLimiter:
    """Synchronous thread-safe token-bucket rate limiter."""

    def __init__(self,
        rate: float,
        *,
        capacity: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._clock: Callable[[],
     float] = clock if clock is not None else time.monotonic
        self.rate = AsyncRateLimiter._finite_positive(rate, name="rate")
        raw_capacity = max(1.0, self.rate) if capacity is None else capacity
        self.capacity = AsyncRateLimiter._finite_positive(raw_capacity, name="capacity")
        self._tokens = self.capacity
        self._updated = self._clock()
        self._lock = threading.Lock()

    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens

    def _refill(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._updated)
        try:
            tokens = self._tokens + elapsed * self.rate
        except OverflowError:
            tokens = self.capacity
        self._tokens = min(self.capacity, tokens)
        self._updated = now

    def reset(self) -> None:
        """Reset the token bucket to full capacity."""
        with self._lock:
            self._tokens = self.capacity
            self._updated = self._clock()

    def try_acquire(self,
        tokens: float = 1.0,
    ) -> bool:
        """Consume tokens immediately if available without waiting."""
        tokens = AsyncRateLimiter._finite_positive(tokens, name="tokens")
        if tokens > self.capacity:
            raise ValueError("tokens must be positive and <= capacity")
        with self._lock:
            self._refill()
            if self._tokens < tokens:
                return False
            self._tokens -= tokens
            return True

    def acquire(self,
        tokens: float = 1.0,
        *,
        timeout: float | None = None,
    ) -> None:
        """Wait until tokens are available or timeout expires."""
        tokens = AsyncRateLimiter._finite_positive(tokens, name="tokens")
        if tokens > self.capacity:
            raise ValueError("tokens must be positive and <= capacity")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 <= timeout <= sys.float_info.max
        ):
            raise ValueError("timeout must be a finite non-negative number or None")

        deadline = (self._clock() + timeout) if timeout is not None else None
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait = deficit / self.rate

            if deadline is not None:
                budget = deadline - self._clock()
                if budget <= 0 or wait > budget or not math.isfinite(wait):
                    raise TimeoutError("rate-limit acquisition timed out")
                sleep_time = min(wait, budget)
            else:
                sleep_time = wait
            time.sleep(sleep_time)

    def __enter__(self) -> RateLimiter:
        self.acquire()
        return self

    def __exit__(self,
        *args: object,
    ) -> None:
        return None


class LeakyBucket:
    """Classic leaky bucket rate limiter smoothing traffic into steady intervals."""

    def __init__(self,
        capacity: int,
        leak_rate: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be a positive integer")
        if (
            isinstance(leak_rate, bool)
            or not isinstance(leak_rate, (int, float))
            or leak_rate <= 0
            or not math.isfinite(float(leak_rate))
        ):
            raise ValueError("leak_rate must be a finite positive number")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self.capacity = capacity
        self.leak_rate = float(leak_rate)
        self._clock = clock if clock is not None else time.monotonic
        self._water = 0.0
        self._last_leak = self._clock()
        self._lock = threading.Lock()

    @property
    def current_level(self) -> float:
        with self._lock:
            self._leak()
            return self._water

    def _leak(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last_leak)
        leaked = elapsed * self.leak_rate
        self._water = max(0.0, self._water - leaked)
        self._last_leak = now

    def try_acquire(self,
        amount: float = 1.0,
    ) -> bool:
        """Attempt to add water to bucket; returns False if it would overflow."""
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            self._leak()
            if self._water + amount > self.capacity:
                return False
            self._water += amount
            return True

    def acquire(self,
        amount: float = 1.0,
        timeout: float | None = None,
    ) -> bool:
        """Wait until water level drops enough to add amount, or until timeout."""
        if amount <= 0 or amount > self.capacity:
            raise ValueError(
                f"amount must be positive and <= capacity ({self.capacity})")
        start = self._clock()
        while True:
            if self.try_acquire(amount):
                return True
            with self._lock:
                needed = (self._water + amount) - self.capacity
                wait_time = max(0.001, needed / self.leak_rate)
            if timeout is not None:
                elapsed = self._clock() - start
                if elapsed + wait_time > timeout:
                    time.sleep(max(0.0, timeout - elapsed))
                    return self.try_acquire(amount)
            time.sleep(wait_time)

    def reset(self) -> None:
        """Empty the bucket completely."""
        with self._lock:
            self._water = 0.0
            self._last_leak = self._clock()


class SlidingWindowLog:
    """Sliding-window log rate limiter with exact millisecond precision."""

    def __init__(self,
        max_requests: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if isinstance(
    max_requests,
    bool) or not isinstance(
        max_requests,
         int) or max_requests < 1:
            raise ValueError("max_requests must be a positive integer")
        if (
            isinstance(window_seconds, bool)
            or not isinstance(window_seconds, (int, float))
            or window_seconds <= 0
        ):
            raise ValueError("window_seconds must be a positive number")
        self.max_requests = max_requests
        self.window_seconds = float(window_seconds)
        self._clock = clock if clock is not None else time.monotonic
        self._logs: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _cleanup(self,
        key: str,
        now: float,
    ) -> list[float]:
        threshold = now - self.window_seconds
        log = self._logs.setdefault(key, [])
        valid = [t for t in log if t > threshold]
        self._logs[key] = valid
        return valid

    def allow(self,
        key: str = "default",
        cost: int = 1,
    ) -> bool:
        """Check if cost requests are allowed under key in the current window."""
        if cost <= 0:
            raise ValueError("cost must be a positive integer")
        now = self._clock()
        with self._lock:
            log = self._cleanup(key, now)
            if len(log) + cost <= self.max_requests:
                for _ in range(cost):
                    log.append(now)
                return True
            return False

    def remaining(self,
        key: str = "default",
    ) -> int:
        """Return the remaining allowed requests for key in current window."""
        now = self._clock()
        with self._lock:
            log = self._cleanup(key, now)
            return max(0, self.max_requests - len(log))

    def reset(self,
        key: str | None = None,
    ) -> None:
        """Reset logs for a specific key or all keys."""
        with self._lock:
            if key is None:
                self._logs.clear()
            else:
                self._logs.pop(key, None)


class BurstTokenBucket:
    """Token bucket supporting sustained rate with configurable burst headroom."""

    def __init__(self,
        rate: float,
        base_capacity: float,
        peak_capacity: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if rate <= 0 or base_capacity <= 0 or peak_capacity < base_capacity:
            raise ValueError("invalid burst token bucket parameters")
        self.rate = float(rate)
        self.base_capacity = float(base_capacity)
        self.peak_capacity = float(peak_capacity)
        self._clock = clock if clock is not None else time.monotonic
        self._tokens = self.base_capacity
        self._last_refill = self._clock()
        self._lock = threading.Lock()

    def consume(self,
        tokens: float = 1.0,
    ) -> bool:
        """Attempt to consume tokens. Returns True if granted."""
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        now = self._clock()
        with self._lock:
            elapsed = max(0.0, now - self._last_refill)
            self._tokens = min(self.peak_capacity, self._tokens + elapsed * self.rate)
            self._last_refill = now
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


def rate_limited(
    limiter: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Synchronous decorator enforcing a rate limiter before execution."""
    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            granted = False
            if hasattr(limiter, "try_acquire"):
                granted = limiter.try_acquire()
            elif hasattr(limiter, "allow"):
                granted = limiter.allow()
            elif hasattr(limiter, "consume"):
                granted = limiter.consume()
            elif hasattr(limiter, "acquire"):
                limiter.acquire()
                granted = True

            if not granted:
                raise RateLimitExceeded("rate limit exceeded for call")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def async_rate_limited(
    limiter: Any,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Asynchronous decorator enforcing an async rate limiter before execution."""
    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        async def wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if hasattr(
    limiter,
    "acquire") and asyncio.iscoroutinefunction(
        limiter.acquire):
                await limiter.acquire()
            elif hasattr(limiter, "try_acquire"):
                if not limiter.try_acquire():
                    raise RateLimitExceeded("async rate limit exceeded")
            return await func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    "AsyncRateLimiter",
    "BurstTokenBucket",
    "LeakyBucket",
    "RateLimitExceeded",
    "RateLimiter",
    "SlidingWindowLog",
    "async_rate_limited",
    "rate_limited",
]
