"""Context-aware retry-delay override tests."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from gunz_utils.retry import (
    RetryPolicy,
    async_run_with_retry,
    run_with_retry,
)


class RetryAfterError(RuntimeError):
    """Test exception carrying an exact retry delay."""

    def __init__(self, retry_after: float) -> None:
        super().__init__("rate limited")
        self.retry_after = retry_after


def test_retry_policy_exception_delay_override_honors_retry_after() -> None:
    calls = 0
    sleeps: list[float] = []

    def work() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RetryAfterError(7.0)
        return "ok"

    policy: RetryPolicy[str] = RetryPolicy(
        attempts=2,
        jitter=False,
        delay_override=lambda _attempt, _result, error: (
            error.retry_after
            if isinstance(error, RetryAfterError)
            else None
        ),
    )

    with patch("gunz_utils.retry.time.sleep", side_effect=sleeps.append):
        result = run_with_retry(
            work,
            policy,
        )

    assert result == "ok"
    assert sleeps == [7.0]


def test_retry_policy_result_delay_override_supports_fixed_schedule() -> None:
    values = iter(["pending", "pending", "ready"])
    sleeps: list[float] = []
    schedule = {
        1: 2.0,
        2: 5.0,
    }

    policy: RetryPolicy[str] = RetryPolicy(
        attempts=3,
        retry_if_result=lambda value: value == "pending",
        jitter=False,
        delay_override=lambda attempt, result, _error: (
            schedule[attempt]
            if result == "pending"
            else None
        ),
    )

    with patch("gunz_utils.retry.time.sleep", side_effect=sleeps.append):
        result = run_with_retry(
            lambda: next(values),
            policy,
        )

    assert result == "ready"
    assert sleeps == [2.0, 5.0]


def test_retry_policy_delay_override_none_uses_existing_backoff() -> None:
    policy: RetryPolicy[str] = RetryPolicy(
        base_delay=2.0,
        max_delay=10.0,
        jitter=False,
        delay_override=lambda _attempt, _result, _error: None,
    )

    assert policy.delay(1) == pytest.approx(2.0)
    assert policy.delay(2) == pytest.approx(4.0)
    assert policy.delay(4) == pytest.approx(10.0)


@pytest.mark.parametrize(
    "value",
    [
        -1.0,
        float("inf"),
        float("nan"),
        True,
    ],
)
def test_retry_policy_rejects_invalid_delay_override_values(
    value: float,
) -> None:
    policy: RetryPolicy[str] = RetryPolicy(
        delay_override=lambda _attempt, _result, _error: value,
    )

    with pytest.raises(ValueError, match="delay_override"):
        policy.delay(1)



def test_async_retry_policy_passes_exception_context_to_delay_override() -> None:
    async def scenario() -> tuple[str, list[float]]:
        calls = 0
        sleeps: list[float] = []

        async def work() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RetryAfterError(3.5)
            return "ok"

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        policy: RetryPolicy[str] = RetryPolicy(
            attempts=2,
            jitter=False,
            delay_override=lambda _attempt, _result, error: (
                error.retry_after
                if isinstance(error, RetryAfterError)
                else None
            ),
        )

        with patch(
            "gunz_utils.retry.asyncio.sleep",
            side_effect=fake_sleep,
        ):
            result = await async_run_with_retry(
                work,
                policy,
            )
        return result, sleeps

    result, sleeps = asyncio.run(scenario())

    assert result == "ok"
    assert sleeps == [3.5]
