"""Retry policies for synchronous and asynchronous callables."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import functools
import math
import random
import sys
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
    """_delay() function.

    Parameters
    ----------
    attempt : int
        attempt parameter.
    base_delay : float
        base_delay parameter.
    max_delay : float
        max_delay parameter.
    jitter : bool
        jitter parameter.

    Returns
    -------
    float
        The result of the operation.
    """
    if base_delay == 0 or max_delay == 0:
        delay = 0.0
    elif base_delay >= max_delay:
        delay = float(max_delay)
    else:
        exponent = attempt - 1
        saturation = math.log2(max_delay) - math.log2(base_delay)
        if exponent >= saturation:
            delay = float(max_delay)
        else:
            try:
                delay = min(float(max_delay), math.ldexp(float(base_delay), exponent))
            except OverflowError:
                delay = float(max_delay)
    return random.uniform(0.0, delay) if jitter and delay else delay


def _validate(
    attempts: int,
    base_delay: float,
    max_delay: float,
    timeout: float | None,
) -> None:
    """_validate() function.

    Parameters
    ----------
    attempts : int
        attempts parameter.
    base_delay : float
        base_delay parameter.
    max_delay : float
        max_delay parameter.
    timeout : float | None
        timeout parameter.
    """
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError("attempts must be a positive integer")
    for name, value in (("base_delay", base_delay), ("max_delay", max_delay)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= sys.float_info.max
        ):
            raise ValueError(f"{name} must be a finite non-negative number")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 <= timeout <= sys.float_info.max
    ):
        raise ValueError("timeout must be a finite non-negative number or None")


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
    delay_override: (
        Callable[[int, T | None, BaseException | None], float | None]
        | None
    ) = None

    def __post_init__(self) -> None:
        _validate(
            self.attempts,
            self.base_delay,
            self.max_delay,
            self.timeout,
        )
        if not self.exceptions:
            raise ValueError("exceptions must not be empty")

    def delay(self,
        attempt: int,
        *,
        result: T | None = None,
        error: BaseException | None = None,
    ) -> float:
        """Return the delay after a one-based attempt.

        An explicit delay_override can inspect the attempt plus result/error and
        return an exact non-negative delay. Returning None falls back to the
        configured exponential backoff and jitter.
        """
        if (
            isinstance(attempt, bool)
            or not isinstance(attempt, int)
            or attempt < 1
        ):
            raise ValueError("attempt must be a positive integer")

        if self.delay_override is not None:
            override = self.delay_override(
                attempt,
                result,
                error,
            )
            if override is not None:
                if (
                    isinstance(override, bool)
                    or not isinstance(override, (int, float))
                    or not 0 <= override <= sys.float_info.max
                ):
                    raise ValueError(
                        "delay_override must return a finite "
                        "non-negative number or None"
                    )
                return float(override)

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


def _deadline(
    timeout: float | None,
) -> float | None:
    """_deadline() function.

    Parameters
    ----------
    timeout : float | None
        timeout parameter.

    Returns
    -------
    float | None
        The result of the operation.
    """
    return None if timeout is None else time.monotonic() + timeout


def _has_wait_budget(
    deadline: float | None,
    delay: float,
) -> bool:
    """_has_wait_budget() function.

    Parameters
    ----------
    deadline : float | None
        deadline parameter.
    delay : float
        delay parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
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
    """Run a synchronous operation under an explicit retry policy.

    Parameters
    ----------
    operation : Callable[[], T]
        operation parameter.
    policy : RetryPolicy[T]
        policy parameter.
    on_retry : Callable[[RetryEvent[T]], None] | None
        on_retry parameter.

    Returns
    -------
    T
        The result of the operation.
    """
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
            delay = policy.delay(
                attempt,
                error=exc,
            )
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
                if not _has_wait_budget(deadline, delay):
                    raise
            time.sleep(delay)
            if not _has_wait_budget(deadline, 0.0):
                raise
            continue

        should_retry = (
            policy.retry_if_result is not None
            and policy.retry_if_result(result)
        )
        if not should_retry or attempt == policy.attempts:
            return result
        delay = policy.delay(
            attempt,
            result=result,
        )
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
            if not _has_wait_budget(deadline, delay):
                return result
        time.sleep(delay)
        if not _has_wait_budget(deadline, 0.0):
            return result
    raise RuntimeError("unreachable")


async def async_run_with_retry(
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy[T],
    *,
    on_retry: Callable[[RetryEvent[T]], None] | None = None,
) -> T:
    """Run an async operation under an explicit retry policy.

    Parameters
    ----------
    operation : Callable[[], Awaitable[T]]
        operation parameter.
    policy : RetryPolicy[T]
        policy parameter.
    on_retry : Callable[[RetryEvent[T]], None] | None
        on_retry parameter.

    Returns
    -------
    T
        The result of the operation.
    """
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
            delay = policy.delay(
                attempt,
                error=exc,
            )
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
                if not _has_wait_budget(deadline, delay):
                    raise
            await asyncio.sleep(delay)
            if not _has_wait_budget(deadline, 0.0):
                raise
            continue

        should_retry = (
            policy.retry_if_result is not None
            and policy.retry_if_result(result)
        )
        if not should_retry or attempt == policy.attempts:
            return result
        delay = policy.delay(
            attempt,
            result=result,
        )
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
            if not _has_wait_budget(deadline, delay):
                return result
        await asyncio.sleep(delay)
        if not _has_wait_budget(deadline, 0.0):
            return result
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
    """Retry a synchronous callable within attempt and time budgets.

    Parameters
    ----------
    attempts : int
        attempts parameter.
    exceptions : tuple[type[BaseException], ...]
        exceptions parameter.
    base_delay : float
        base_delay parameter.
    max_delay : float
        max_delay parameter.
    jitter : bool
        jitter parameter.
    retry_if : RetryPredicate | None
        retry_if parameter.
    on_retry : RetryHook | None
        on_retry parameter.
    timeout : float | None
        timeout parameter.

    Returns
    -------
    Callable[[Callable[P, T]], Callable[P, T]]
        The result of the operation.
    """
    _validate(attempts, base_delay, max_delay, timeout)
    if not exceptions:
        raise ValueError("exceptions must not be empty")

    def decorate(
        func: Callable[P, T],
    ) -> Callable[P, T]:
        """decorate() function.

        Parameters
        ----------
        func : Callable[P, T]
            func parameter.

        Returns
        -------
        Callable[P, T]
            The result of the operation.
        """
        @functools.wraps(func)
        def wrapped(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> T:
            """wrapped() function.

            Parameters
            ----------
            args : P.args
                args parameter.
            kwargs : P.kwargs
                kwargs parameter.

            Returns
            -------
            T
                The result of the operation.
            """
            deadline = _deadline(timeout)
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
                    if not _has_wait_budget(deadline, delay):
                        raise
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                        if not _has_wait_budget(deadline, delay):
                            raise
                    time.sleep(delay)
                    if not _has_wait_budget(deadline, 0.0):
                        raise
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
    """Retry an async callable within attempt and time budgets.

    Parameters
    ----------
    attempts : int
        attempts parameter.
    exceptions : tuple[type[BaseException], ...]
        exceptions parameter.
    base_delay : float
        base_delay parameter.
    max_delay : float
        max_delay parameter.
    jitter : bool
        jitter parameter.
    retry_if : RetryPredicate | None
        retry_if parameter.
    on_retry : RetryHook | None
        on_retry parameter.
    timeout : float | None
        timeout parameter.

    Returns
    -------
    Callable[[Callable[P, Any]], Callable[P, Any]]
        The result of the operation.
    """
    _validate(attempts, base_delay, max_delay, timeout)
    if not exceptions:
        raise ValueError("exceptions must not be empty")

    def decorate(
        func: Callable[P, Any],
    ) -> Callable[P, Any]:
        """decorate() function.

        Parameters
        ----------
        func : Callable[P, Any]
            func parameter.

        Returns
        -------
        Callable[P, Any]
            The result of the operation.
        """
        @functools.wraps(func)
        async def wrapped(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> Any:
            """wrapped() function.

            Parameters
            ----------
            args : P.args
                args parameter.
            kwargs : P.kwargs
                kwargs parameter.

            Returns
            -------
            Any
                The result of the operation.
            """
            deadline = _deadline(timeout)
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
                    if not _has_wait_budget(deadline, delay):
                        raise
                    if on_retry is not None:
                        on_retry(exc, attempt, delay)
                        if not _has_wait_budget(deadline, delay):
                            raise
                    await asyncio.sleep(delay)
                    if not _has_wait_budget(deadline, 0.0):
                        raise
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
