"""Deterministic retry budgets and token-bucket numerical boundaries."""

from __future__ import annotations

import asyncio
import importlib
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.retry import RetryEvent, RetryPolicy

rate_limit_module = importlib.import_module("gunz_utils.rate_limit")
retry_module = importlib.import_module("gunz_utils.retry")

RETRY_VARIANTS = (
    "decorator_sync",
    "decorator_async",
    "exception_sync",
    "exception_async",
    "result_sync",
    "result_async",
)


@dataclass
class _Clock:
    now: float = 100.0
    oversleep: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay + self.oversleep

    async def async_sleep(self, delay: float) -> None:
        self.sleep(delay)


@contextmanager
def _retry_clock(clock: _Clock) -> Iterator[None]:
    # Replace module references, preserving the event loop's real clock/sleep.
    with (
        patch.object(
            retry_module,
            "time",
            SimpleNamespace(monotonic=clock.monotonic, sleep=clock.sleep),
        ),
        patch.object(
            retry_module,
            "asyncio",
            SimpleNamespace(
                sleep=clock.async_sleep,
                CancelledError=asyncio.CancelledError,
            ),
        ),
    ):
        yield


def _exercise_retry(
    variant: str,
    clock: _Clock,
    policy: RetryPolicy[str],
    on_retry: Callable[[RetryEvent[str]], None] | None = None,
) -> list[float]:
    """Exercise each public adapter with the same retryable last outcome."""
    calls: list[float] = []
    original_error = OSError("original operation failure")

    def operation() -> str:
        calls.append(clock.now)
        if variant.startswith("result"):
            return "pending"
        raise original_error

    async def async_operation() -> str:
        return operation()

    def execute() -> str:
        if variant.startswith("decorator"):
            def hook(error: BaseException, attempt: int, delay: float) -> None:
                if on_retry is not None:
                    on_retry(RetryEvent(attempt=attempt, delay=delay, error=error))

            decorator = (
                retry_module.async_retry
                if variant.endswith("async")
                else retry_module.retry
            )(
                attempts=policy.attempts,
                exceptions=policy.exceptions,
                base_delay=policy.base_delay,
                max_delay=policy.max_delay,
                jitter=policy.jitter,
                timeout=policy.timeout,
                retry_if=policy.retry_if_exception,
                on_retry=hook if on_retry is not None else None,
            )
            if variant.endswith("async"):
                return asyncio.run(decorator(async_operation)())
            return decorator(operation)()

        if variant.endswith("async"):
            return asyncio.run(
                retry_module.async_run_with_retry(
                    async_operation, policy, on_retry=on_retry
                )
            )
        return retry_module.run_with_retry(operation, policy, on_retry=on_retry)

    with _retry_clock(clock):
        if variant.startswith("result"):
            assert execute() == "pending"
        else:
            with pytest.raises(OSError) as caught:
                execute()
            assert caught.value is original_error
    return calls


@pytest.mark.parametrize("variant", RETRY_VARIANTS)
@pytest.mark.parametrize("hook_duration", [0.75, 1.5, 2.0])
def test_retry_hook_cannot_sleep_beyond_remaining_budget(
    variant: str, hook_duration: float
) -> None:
    clock = _Clock()
    events: list[RetryEvent[str]] = []

    def hook(event: RetryEvent[str]) -> None:
        events.append(event)
        clock.now += hook_duration

    calls = _exercise_retry(
        variant,
        clock,
        RetryPolicy(
            attempts=2,
            base_delay=1.0,
            jitter=False,
            timeout=1.5,
            retry_if_result=lambda result: True,
        ),
        hook,
    )
    assert calls == [100.0]
    assert clock.sleeps == []
    assert len(events) == 1
    assert events[0].delay == 1.0


@pytest.mark.parametrize("variant", RETRY_VARIANTS)
def test_retry_hook_with_enough_budget_still_retries(variant: str) -> None:
    clock = _Clock()

    def hook(event: RetryEvent[str]) -> None:
        clock.now += 0.25

    calls = _exercise_retry(
        variant,
        clock,
        RetryPolicy(
            attempts=2,
            base_delay=1.0,
            jitter=False,
            timeout=2.0,
            retry_if_result=lambda result: True,
        ),
        hook,
    )
    assert calls == [100.0, 101.25]
    assert clock.sleeps == [1.0]


@pytest.mark.parametrize("variant", RETRY_VARIANTS)
@pytest.mark.parametrize("oversleep", [0.0, 0.5])
def test_retry_does_not_start_at_or_after_deadline(
    variant: str, oversleep: float
) -> None:
    clock = _Clock(oversleep=oversleep)
    calls = _exercise_retry(
        variant,
        clock,
        RetryPolicy(
            attempts=2,
            base_delay=1.0,
            jitter=False,
            timeout=1.0,
            retry_if_result=lambda result: True,
        ),
    )
    assert calls == [100.0]
    assert clock.sleeps == [1.0]


@pytest.mark.parametrize("variant", RETRY_VARIANTS)
def test_retry_zero_timeout_preserves_first_attempt(variant: str) -> None:
    clock = _Clock()
    calls = _exercise_retry(
        variant,
        clock,
        RetryPolicy(
            attempts=2,
            base_delay=0.0,
            timeout=0.0,
            retry_if_result=lambda result: True,
        ),
    )
    assert calls == [100.0]
    assert clock.sleeps == []


@pytest.mark.parametrize("variant", RETRY_VARIANTS)
def test_retry_predicate_time_counts_against_budget(variant: str) -> None:
    clock = _Clock()

    def predicate(value: object) -> bool:
        clock.now += 2.0
        return True

    calls = _exercise_retry(
        variant,
        clock,
        RetryPolicy(
            attempts=2,
            base_delay=0.5,
            jitter=False,
            timeout=1.0,
            retry_if_exception=predicate,
            retry_if_result=predicate,
        ),
    )
    assert calls == [100.0]
    assert clock.sleeps == []


@pytest.mark.parametrize("variant", RETRY_VARIANTS[2:])
def test_retry_delay_override_time_counts_against_budget(variant: str) -> None:
    clock = _Clock()

    def override(
        attempt: int, result: str | None, error: BaseException | None
    ) -> float:
        clock.now += 2.0
        return 0.5

    calls = _exercise_retry(
        variant,
        clock,
        RetryPolicy(
            attempts=2,
            timeout=1.0,
            retry_if_result=lambda result: True,
            delay_override=override,
        ),
    )
    assert calls == [100.0]
    assert clock.sleeps == []


@pytest.mark.parametrize("use_decorator", [False, True])
def test_async_retry_preserves_cancellation_with_broad_exception_policy(
    use_decorator: bool,
) -> None:
    clock = _Clock()
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError

    with _retry_clock(clock), pytest.raises(asyncio.CancelledError):
        if use_decorator:
            wrapped = retry_module.async_retry(
                attempts=2, base_delay=0, exceptions=(BaseException,)
            )(operation)
            asyncio.run(wrapped())
        else:
            asyncio.run(
                retry_module.async_run_with_retry(
                    operation,
                    RetryPolicy(attempts=2, base_delay=0, exceptions=(BaseException,)),
                )
            )
    assert calls == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("value", [10**400, -(10**400)])
@pytest.mark.parametrize("name", ["base_delay", "max_delay", "timeout"])
@pytest.mark.parametrize(
    "factory", [RetryPolicy, retry_module.retry, retry_module.async_retry]
)
def test_retry_rejects_unrepresentable_timing_as_value_error(
    value: int, name: str, factory: Callable[..., object]
) -> None:
    with pytest.raises(ValueError, match=name):
        factory(**{name: value})


@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_retry_rejects_unrepresentable_delay_override_as_value_error(
    value: int,
) -> None:
    policy: RetryPolicy[str] = RetryPolicy(delay_override=lambda *_: value)
    with pytest.raises(ValueError, match="delay_override"):
        policy.delay(1)


@contextmanager
def _stationary_limiter_clock() -> Iterator[None]:
    async def unexpected_sleep(delay: float) -> None:
        pytest.fail(f"immediate acquisition unexpectedly requested sleep({delay})")

    with (
        patch.object(
            rate_limit_module, "time", SimpleNamespace(monotonic=lambda: 100.0)
        ),
        patch.object(
            rate_limit_module,
            "asyncio",
            SimpleNamespace(Lock=asyncio.Lock, sleep=unexpected_sleep),
        ),
    ):
        yield


@pytest.mark.parametrize("method", ["try_acquire", "acquire"])
def test_rate_limiter_rejects_integer_above_capacity_before_rounding(
    method: str,
) -> None:
    async def scenario() -> None:
        with _stationary_limiter_clock():
            capacity = 2**53
            limiter = AsyncRateLimiter(1, capacity=capacity)
            request = capacity + 1
            # An exact integer oracle: the request exceeds a full bucket.
            assert request > capacity
            assert float(request) == float(capacity)
            with pytest.raises(ValueError, match="capacity"):
                await getattr(limiter, method)(request)
            assert limiter.available_tokens == capacity
            outcome = await getattr(limiter, method)(capacity)
            assert outcome is (True if method == "try_acquire" else None)
            assert limiter.available_tokens == 0.0

    asyncio.run(scenario())


@pytest.mark.parametrize("method", ["try_acquire", "acquire"])
def test_rate_limiter_normalizes_accepted_integer_request_arithmetic(
    method: str,
) -> None:
    async def scenario() -> None:
        with _stationary_limiter_clock():
            request = 2**53 + 1
            capacity = request + 1
            limiter = AsyncRateLimiter(1, capacity=capacity)
            await limiter.acquire(1)
            # These two integer requests exactly consume the initial capacity.
            outcome = await getattr(limiter, method)(request)
            assert outcome is (True if method == "try_acquire" else None)
            assert limiter.available_tokens == 0.0

    asyncio.run(scenario())


@pytest.mark.parametrize("value", [10**400, -(10**400)])
@pytest.mark.parametrize("name", ["rate", "capacity"])
def test_rate_limiter_rejects_unrepresentable_constructor_values(
    value: int, name: str
) -> None:
    with pytest.raises(ValueError, match=name):
        if name == "rate":
            AsyncRateLimiter(value)
        else:
            AsyncRateLimiter(1, capacity=value)


@pytest.mark.parametrize("value", [10**400, -(10**400)])
@pytest.mark.parametrize("method", ["try_acquire", "acquire"])
def test_rate_limiter_rejects_unrepresentable_requests_atomically(
    value: int, method: str
) -> None:
    async def scenario() -> None:
        with _stationary_limiter_clock():
            limiter = AsyncRateLimiter(1)
            with pytest.raises(ValueError, match="tokens"):
                await getattr(limiter, method)(value)
            assert limiter.available_tokens == 1.0

    asyncio.run(scenario())


@pytest.mark.parametrize("value", [10**400, -(10**400)])
def test_rate_limiter_rejects_unrepresentable_timeout_atomically(value: int) -> None:
    async def scenario() -> None:
        with _stationary_limiter_clock():
            limiter = AsyncRateLimiter(1)
            with pytest.raises(ValueError, match="timeout"):
                await limiter.acquire(timeout=value)
            assert limiter.available_tokens == 1.0

    asyncio.run(scenario())


def test_largest_finite_float_parameters_remain_valid() -> None:
    maximum = sys.float_info.max
    policy = RetryPolicy(
        base_delay=maximum, max_delay=maximum, timeout=maximum, jitter=False
    )
    assert policy.delay(1) == maximum

    async def scenario() -> None:
        with _stationary_limiter_clock():
            limiter = AsyncRateLimiter(maximum, capacity=maximum)
            await limiter.acquire(maximum, timeout=0)
            assert limiter.available_tokens == 0.0

    asyncio.run(scenario())
