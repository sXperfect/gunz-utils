"""Phase 47 security-lane re-audit regression tests (round 6).

Re-audits of previously-covered modules (instrumentation, sync, signals,
subprocess, dag, retry) for overlooked defects:

1. dag -- ``_validate_rollback_timeout`` (dag.py:153) calls
   ``math.isfinite(timeout)`` directly on the raw value. A huge integer such as
   ``10**400`` makes ``math.isfinite`` raise ``OverflowError`` (int too large to
   convert to float) instead of the documented ``ValueError``, leaking an
   internal ``OverflowError`` from ``WorkflowDAG(...)`` and ``async_execute``.

2. dag -- synchronous rollback (``_rollback_sync``, dag.py:306-319) closes a
   coroutine returned by ``compensate`` but leaves a *non-coroutine* awaitable
   neither awaited nor closed: it is leaked as a pending awaitable and the
   stage is misreported as a TypeError. Exception-safety/cleanup gap.
"""

from __future__ import annotations

import pytest

from gunz_utils.dag import (
    WorkflowDAG,
    WorkflowExecutionError,
    WorkflowStage,
    _validate_rollback_timeout,
)


def test_dag_rollback_timeout_huge_int_raises_valueerror() -> None:
    """An int too large for float must surface ValueError, not OverflowError."""
    with pytest.raises(ValueError):
        _validate_rollback_timeout(10**400)
    with pytest.raises(ValueError):
        WorkflowDAG(
            [WorkflowStage("a", run=lambda deps: 1)],
            rollback_timeout=10**400,
        )


def test_dag_sync_rollback_does_not_leak_noncoroutine_awaitable() -> None:
    """A non-coroutine awaitable from compensate must be awaited or closed.

    The synchronous rollback path only closes coroutines; a custom awaitable
    (not a coroutine) is neither awaited nor closed, so it leaks as a pending
    awaitable and the stage is misreported as a TypeError.
    """

    class RecordingAwaitable:
        def __init__(self) -> None:
            self.awaited = False
            self.closed = False

        def __await__(self):  # pragma: no cover - exercised by the fix
            self.awaited = True
            yield

    leaked = RecordingAwaitable()

    def compensate(_output: object) -> RecordingAwaitable:
        return leaked

    def boom(_deps: object) -> object:
        raise RuntimeError("boom")

    dag = WorkflowDAG(
        [
            WorkflowStage(
                "a",
                run=lambda deps: 1,
                compensate=compensate,
            ),
            WorkflowStage("b", run=boom, dependencies=("a",)),
        ]
    )
    with pytest.raises(WorkflowExecutionError):
        dag.execute()
    # The pending awaitable must have been either awaited or closed so it is
    # not leaked with a never-run __await__.
    assert leaked.awaited or leaked.closed  # RED: neither happens today
