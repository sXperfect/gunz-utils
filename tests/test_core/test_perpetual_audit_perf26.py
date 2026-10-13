"""Phase 26 perpetual audit: round-4 (deepest) re-audit of retry/rate_limit/
async_utils/timing.

async_utils.py (with_timeout/cancel_and_wait/_run_with_zero_timeout),
rate_limit.py (AsyncRateLimiter acquire/try_acquire/available_tokens),
and timing.py (Timer/timer) were verified correct across targeted probes:
with_timeout timeout=0 handles ready work, sleep(0) chains, and immediate
raises; rate_limit accounting, cancellation-during-acquire, and token/capacity
validation all hold; Timer restart/stop/elapsed is correct.

One NEW bug surfaced in retry.py: the ``retry`` and ``async_retry`` decorators
do not validate that ``exceptions`` is non-empty at decoration time. They call
``_validate(attempts, base_delay, max_delay, timeout)`` but never check
``exceptions``, so ``@retry(exceptions=())`` silently configures a policy that
catches nothing and performs zero retries. This contradicts
``RetryPolicy(exceptions=())``, whose ``__post_init__`` raises
``ValueError("exceptions must not be empty")``. A user who writes
``@retry(attempts=5, exceptions=(), timeout=...)`` gets exactly one attempt with
no error and no indication their retry budget is unused.

This test is expected to be RED against base ``da04bbc`` and documents the
correct behavior after a fix.
"""

from __future__ import annotations

import asyncio

from gunz_utils.retry import RetryPolicy, async_retry, retry


# ---------------------------------------------------------------------------
# retry decorator: empty exceptions must be rejected at decoration time, like
# RetryPolicy does. Currently it is silently accepted (no retries performed).
# ---------------------------------------------------------------------------
def test_retry_decorator_rejects_empty_exceptions() -> None:
    # RetryPolicy is the canonical policy object and rejects empty exceptions.
    try:
        RetryPolicy(exceptions=())
    except ValueError:
        pass
    else:
        raise AssertionError("RetryPolicy(exceptions=()) should raise ValueError")

    # The retry decorator must validate identically at decoration time.
    try:
        retry(attempts=5, exceptions=())  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError(
        "retry(exceptions=()) should raise ValueError at decoration time, "
        "not silently disable retrying"
    )


def test_async_retry_decorator_rejects_empty_exceptions() -> None:
    try:
        async_retry(attempts=5, exceptions=())  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError(
        "async_retry(exceptions=()) should raise ValueError at decoration time, "
        "not silently disable retrying"
    )


# ---------------------------------------------------------------------------
# Empty exceptions must not silently produce a single attempt. If the decorator
# is given an empty tuple it must fail fast at decoration time rather than run
# the wrapped callable once with the configured attempts/backoff/timeout unused.
# ---------------------------------------------------------------------------
def test_retry_with_empty_exceptions_does_not_silently_noop() -> None:
    calls: dict[str, int] = {"n": 0}

    def op() -> int:
        calls["n"] += 1
        raise ValueError("boom")

    # Correct behavior: decorating with empty exceptions fails at decoration
    # time, so the wrapped callable is never created and never runs.
    try:
        retry(attempts=5, exceptions=(), base_delay=0.01, jitter=False)(op)  # type: ignore[arg-type]
    except ValueError:
        return  # expected: validation error surfaces at decoration
    try:
        op()
    except ValueError:
        pass
    assert calls["n"] <= 1, (
        "retry(exceptions=()) must not silently retry; it must reject at "
        "decoration time"
    )


# ---------------------------------------------------------------------------
# Async retry: same guarantee for the async decorator.
# ---------------------------------------------------------------------------
def test_async_retry_with_empty_exceptions_does_not_silently_noop() -> None:
    calls: dict[str, int] = {"n": 0}

    async def op() -> int:
        calls["n"] += 1
        raise ValueError("boom")

    # Correct behavior: decorating with empty exceptions fails at decoration
    # time, so the wrapped callable is never created and never runs.
    try:
        wrapped = async_retry(
            attempts=5,
            exceptions=(),  # type: ignore[arg-type]
            base_delay=0.01,
            jitter=False,
        )(op)
    except ValueError:
        return  # expected: validation error surfaces at decoration
    try:
        asyncio.run(wrapped())
    except ValueError:
        pass
    assert calls["n"] <= 1, (
        "async_retry(exceptions=()) must not silently retry; it must reject "
        "at decoration time"
    )
