"""Retry policies for synchronous and asynchronous callables."""

from __future__ import annotations

import asyncio
import functools
import random
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")
RetryHook = Callable[[BaseException, int, float], None]
RetryPredicate = Callable[[BaseException], bool]


def _delay(attempt: int, base_delay: float, max_delay: float, jitter: bool) -> float:
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    return random.uniform(0.0, delay) if jitter and delay else delay


def retry(
    *,
    attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.1,
    max_delay: float = 10.0,
    jitter: bool = True,
    retry_if: RetryPredicate | None = None,
    on_retry: RetryHook | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a synchronous callable with bounded exponential backoff."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if base_delay < 0 or max_delay < 0:
        raise ValueError("delays must be non-negative")

    def decorate(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts or (
                        retry_if is not None and not retry_if(exc)
                    ):
                        raise
                    delay = _delay(attempt, base_delay, max_delay, jitter)
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                    time.sleep(delay)
            raise RuntimeError("unreachable")

        return wrapped

    return decorate


def async_retry(
    *,
    attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.1,
    max_delay: float = 10.0,
    jitter: bool = True,
    retry_if: RetryPredicate | None = None,
    on_retry: RetryHook | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Retry an async callable while preserving cancellation."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if base_delay < 0 or max_delay < 0:
        raise ValueError("delays must be non-negative")

    def decorate(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> Any:
            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except asyncio.CancelledError:
                    raise
                except exceptions as exc:
                    if attempt == attempts or (
                        retry_if is not None and not retry_if(exc)
                    ):
                        raise
                    delay = _delay(attempt, base_delay, max_delay, jitter)
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                    await asyncio.sleep(delay)
            raise RuntimeError("unreachable")

        return wrapped

    return decorate


__all__ = ["async_retry", "retry"]
