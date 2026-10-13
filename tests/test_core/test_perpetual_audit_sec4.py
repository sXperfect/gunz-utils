"""Perpetual security & concurrency audit - PHASE 4 regression tests.

Each test exposes a concrete correctness, resource-leak, or resilience-bound
defect in the audited modules (upstream_protocol, faults, resilience, dag,
plugins). Tests are written to FAIL ("red") against the current source and must
pass only after the corresponding production fix lands. Production code is
intentionally not modified.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import inspect
import time

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.dag import WorkflowDAG, WorkflowStage
from gunz_utils.upstream_protocol import (
    BaseUpstream,
    PolicyUpstream,
    UpstreamUnavailableError,
)

# -----------------------------------------------------------------------------
# dag.py - synchronous execute() leaks an unawaited coroutine for async run
# -----------------------------------------------------------------------------


def test_sync_execute_does_not_leak_unawaited_coroutine_for_async_run() -> None:
    """Sync ``execute()`` must never return a raw coroutine as a stage output.

    ``WorkflowStage.run`` is documented as "May be synchronous or an async
    coroutine function", yet the synchronous ``WorkflowDAG.execute()`` invokes
    ``stage.run(...)`` and stores the result verbatim without checking
    ``inspect.isawaitable``. An async ``run`` therefore produces an unawaited
    (and never closed) coroutine as the stage output and cache value, emitting
    a ``RuntimeWarning: coroutine ... was never awaited`` and returning a
    garbage result. ``_rollback_sync`` already guards the analogous async
    ``compensate`` case by closing the coroutine and raising a clear
    ``TypeError``; ``execute()`` fails to do the equivalent for ``run``.
    """
    async def async_run(deps):  # documented: async run is supported
        return "expected-value"

    dag = WorkflowDAG(
        [WorkflowStage(name="a", run=async_run)],
    )
    result = dag.execute()

    out = result["a"]
    assert not inspect.iscoroutine(out), (
        "sync execute() leaked an unawaited coroutine for an async stage run "
        "(coroutine was never awaited and never closed)"
    )
    assert out == "expected-value"


# -----------------------------------------------------------------------------
# upstream_protocol.py - retry loop issues back-to-back requests with no backoff
# -----------------------------------------------------------------------------


class _FlakyUpstream(BaseUpstream):
    """Upstream that records call timestamps and always reports unavailable."""

    name = "flaky"

    def __init__(self) -> None:
        self.times: list[float] = []

    async def _invoke(self, tool_name, arguments):
        self.times.append(time.monotonic())
        raise UpstreamUnavailableError("down", upstream=self.name)


def test_retry_applies_backoff_between_attempts() -> None:
    """Retries on ``UpstreamUnavailableError`` must not be issued back-to-back.

    ``PolicyUpstream.call`` retries unavailable upstreams in a tight loop with
    zero delay/jitter between attempts (no ``retry_delay`` mechanism exists and
    the total wall time is unbounded, capped only by ``attempts * timeout``).
    Under an upstream outage a single logical call hammers the failing service
    ``max_attempts`` times in immediate succession, amplifying load (a retry
    storm) instead of giving the peer time to recover.
    """
    async def scenario() -> list[float]:
        client = _FlakyUpstream()
        policy = PolicyUpstream(
            client,
            max_attempts=5,
            idempotent_tools=frozenset({"tool"}),
        )
        with pytest.raises(UpstreamUnavailableError):
            await policy.call("tool", {})
        return client.times

    times = _run(scenario())
    gaps = [b - a for a, b in zip(times, times[1:], strict=False)]
    assert len(times) == 5, f"expected 5 attempts, got {len(times)}"
    assert min(gaps) >= 0.005, (
        f"retries issued with zero backoff between attempts (gaps={gaps!r})"
    )


# -----------------------------------------------------------------------------
# dag.py - sync rollback correctly rejects async compensate (sanity green)
# -----------------------------------------------------------------------------


def test_sync_rollback_reports_async_compensate_as_error() -> None:
    """The synchronous rollback guard for async ``compensate`` is green.

    Sanity check confirming the framework already closes an unawaited
    compensation coroutine and surfaces a ``TypeError`` instead of silently
    storing it, which is the behaviour ``execute()`` should mirror for ``run``.
    """
    async def async_run(deps):
        return "v"

    async def async_compensate(out):
        return None

    dag = WorkflowDAG(
        [
            WorkflowStage(
                name="a",
                run=async_run,
                compensate=async_compensate,
            ),
            WorkflowStage(
                name="b",
                run=lambda deps: (_ for _ in ()).throw(ValueError("boom")),
                dependencies=("a",),
            ),
        ],
    )
    with pytest.raises(Exception) as exc_info:
        dag.execute()

    err = exc_info.value
    assert err.stage_name == "b"
    compensation_errors = tuple(err.compensation_errors or ())
    assert compensation_errors, "expected a recorded compensation error"
    assert isinstance(compensation_errors[0][1], TypeError)
    assert "asynchronous compensation" in str(compensation_errors[0][1])


def _run(coro):
    import asyncio
    return asyncio.run(coro)
