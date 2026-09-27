"""Retry policies for synchronous and asynchronous callables."""

from __future__ import annotations

import asyncio
import functools
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Generic, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")
RetryHook = Callable[[BaseException, int, float], None]
RetryPredicate = Callable[[BaseException], bool]


def _delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    jitter: bool,
) -> float:
    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    return random.uniform(0.0, delay) if jitter and delay else delay


def _validate(
    attempts: int,
    base_delay: float,
    max_delay: float,
    timeout: float | None,
) -> None:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if base_delay < 0 or max_delay < 0:
        raise ValueError("delays must be non-negative")
    if timeout is not None and timeout < 0:
        raise ValueError("timeout must be non-negative")


@dataclass(frozen=True, slots=True)
class RetryPolicy(Generic[T]):
    """Policy for retrying on exceptions, results, or both."""

    attempts: int = 3
    exceptions: tuple[type[BaseException], ...] = (Exception,)
    base_delay: float = 0.1
    max_delay: float = 10.0
    jitter: bool = True
    timeout: float | None = None
    retry_if_exception: Callable[[BaseException], bool] | None = None
    retry_if_result: Callable[[T], bool] | None = None

    def __post_init__(self) -> None:
        _validate(
            self.attempts,
            self.base_delay,
            self.max_delay,
            self.timeout,
        )
        if not self.exceptions:
            raise ValueError("exceptions must not be empty")

    def delay(self, attempt: int) -> float:
        """Return the configured delay after a one-based attempt."""
        if attempt < 1:
            raise ValueError("attempt must be at least 1")
        return _delay(
            attempt,
            self.base_delay,
            self.max_delay,
            self.jitter,
        )


@dataclass(frozen=True, slots=True)
class RetryEvent(Generic[T]):
    """Observation emitted immediately before a retry sleep."""

    attempt: int
    delay: float
    result: T | None = None
    error: BaseException | None = None


def _deadline(timeout: float | None) -> float | None:
    return None if timeout is None else time.monotonic() + timeout


def _has_wait_budget(deadline: float | None, delay: float) -> bool:
    if deadline is None:
        return True
    remaining = deadline - time.monotonic()
    return remaining > 0 and delay <= remaining


def run_with_retry(
    operation: Callable[[], T],
    policy: RetryPolicy[T],
    *,
    on_retry: Callable[[RetryEvent[T]], None] | None = None,
) -> T:
    """Run a synchronous operation under an explicit retry policy."""
    deadline = _deadline(policy.timeout)
    for attempt in range(1, policy.attempts + 1):
        try:
            result = operation()
        except policy.exceptions as exc:
            if attempt == policy.attempts:
                raise
            if (
                policy.retry_if_exception is not None
                and not policy.retry_if_exception(exc)
            ):
                raise
            delay = policy.delay(attempt)
            if not _has_wait_budget(deadline, delay):
                raise
            if on_retry is not None:
                on_retry(
                    RetryEvent(
                        attempt=attempt,
                        delay=delay,
                        error=exc,
                    )
                )
            time.sleep(delay)
            continue

        should_retry = (
            policy.retry_if_result is not None
            and policy.retry_if_result(result)
        )
        if not should_retry or attempt == policy.attempts:
            return result
        delay = policy.delay(attempt)
        if not _has_wait_budget(deadline, delay):
            return result
        if on_retry is not None:
            on_retry(
                RetryEvent(
                    attempt=attempt,
                    delay=delay,
                    result=result,
                )
            )
        time.sleep(delay)
    raise RuntimeError("unreachable")


async def async_run_with_retry(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy[T],
    *,
    on_retry: Callable[[RetryEvent[T]], None] | None = None,
) -> T:
    """Run an async operation under an explicit retry policy."""
    deadline = _deadline(policy.timeout)
    for attempt in range(1, policy.attempts + 1):
        try:
            result = await operation()
        except asyncio.CancelledError:
            raise
        except policy.exceptions as exc:
            if attempt == policy.attempts:
                raise
            if (
                policy.retry_if_exception is not None
                and not policy.retry_if_exception(exc)
            ):
                raise
            delay = policy.delay(attempt)
            if not _has_wait_budget(deadline, delay):
                raise
            if on_retry is not None:
                on_retry(
                    RetryEvent(
                        attempt=attempt,
                        delay=delay,
                        error=exc,
                    )
                )
            await asyncio.sleep(delay)
            continue

        should_retry = (
            policy.retry_if_result is not None
            and policy.retry_if_result(result)
        )
        if not should_retry or attempt == policy.attempts:
            return result
        delay = policy.delay(attempt)
        if not _has_wait_budget(deadline, delay):
            return result
        if on_retry is not None:
            on_retry(
                RetryEvent(
                    attempt=attempt,
                    delay=delay,
                    result=result,
                )
            )
        await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


def retry(
    *,
    attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    base_delay: float = 0.1,
    max_delay: float = 10.0,
    jitter: bool = True,
    retry_if: RetryPredicate | None = None,
    on_retry: RetryHook | None = None,
    timeout: float | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a synchronous callable within attempt and time budgets."""
    _validate(attempts, base_delay, max_delay, timeout)

    def decorate(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
            deadline = None if timeout is None else time.monotonic() + timeout
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == attempts or (
                        retry_if is not None and not retry_if(exc)
                    ):
                        raise
                    delay = _delay(
                        attempt,
                        base_delay,
                        max_delay,
                        jitter,
                    )
                    if deadline is not None:
                        budget = deadline - time.monotonic()
                        if budget <= 0 or delay > budget:
                            raise
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
    timeout: float | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """Retry an async callable within attempt and time budgets."""
    _validate(attempts, base_delay, max_delay, timeout)

    def decorate(func: Callable[P, Any]) -> Callable[P, Any]:
        @functools.wraps(func)
        async def wrapped(*args: P.args, **kwargs: P.kwargs) -> Any:
            deadline = None if timeout is None else time.monotonic() + timeout
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
                    delay = _delay(
                        attempt,
                        base_delay,
                        max_delay,
                        jitter,
                    )
                    if deadline is not None:
                        budget = deadline - time.monotonic()
                        if budget <= 0 or delay > budget:
                            raise
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                    await asyncio.sleep(delay)
            raise RuntimeError("unreachable")

        return wrapped

    return decorate


__all__ = [
    "RetryEvent",
    "RetryPolicy",
    "async_retry",
    "async_run_with_retry",
    "retry",
    "run_with_retry",
]
