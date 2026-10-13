"""Perpetual security & concurrency audit - PHASE 17 (round-3) regression tests.

Round-3 re-audit of concurrency, io, dag, and leases (the deepest deferred/NEW
issues two prior passes missed). Tests are written to FAIL ("red") against the
current source (base 23d70e7, which already contains the phase 1-16 fixes) and
must pass only after the corresponding production fix lands. Production code is
intentionally not modified.

Findings covered here (NEW, not previously flagged):
1. ``WorkflowDAG.effective_fingerprint`` (dag.py:219-261) computes each stage's
   transitive fingerprint with a *recursive* ``resolve`` helper, recursing once
   per dependency. A deep (linear) DAG that validates and topologically orders
   fine - ``_topological_order`` is deliberately iterative (dag.py:169) so deep
   acyclic DAGs do not blow the Python stack - blows the stack at fingerprint
   time with ``RecursionError``. ``effective_fingerprint`` is invoked for every
   stage in both ``execute`` and ``async_execute``, so a deep DAG is unusable.
2. ``gather_limited`` (concurrency.py:104-118) does not honor
   ``return_exceptions=True`` for a subtask that raises ``CancelledError``:
   ``task.result()`` raises and the ``except asyncio.CancelledError: raise``
   re-raises it, aborting the whole gather and discarding the already-collected
   results of the other subtasks. ``asyncio.gather(..., return_exceptions=True)``
   returns the ``CancelledError`` as a result and continues; ``gather_limited``
   must do the same so a single cancelled subtask cannot silently destroy the
   other results.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import asyncio
import sys

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.concurrency import gather_limited
from gunz_utils.dag import WorkflowDAG, WorkflowStage

# -----------------------------------------------------------------------------
# dag.py - effective_fingerprint recurses on deep DAGs and blows the stack
# -----------------------------------------------------------------------------


def _deep_chain_dag(depth: int) -> tuple[WorkflowDAG, str]:
    """Build a linear chain A0 <- A1 <- ... of ``depth`` fingerprinted stages."""
    stages: list[WorkflowStage] = []
    previous: str | None = None
    for index in range(depth):
        name = f"s{index}"
        dependencies = (previous,) if previous is not None else ()
        stages.append(
            WorkflowStage(
                name=name,
                run=lambda _d, i=index: i,
                dependencies=dependencies,
                fingerprint=f"f{index}",
            )
        )
        previous = name
    return WorkflowDAG(stages), str(previous)


def test_effective_fingerprint_deep_dag_no_recursion_error() -> None:
    """``effective_fingerprint`` must handle a deep DAG without RecursionError.

    ``_topological_order`` (dag.py:169) is iterative so a deep acyclic DAG
    orders fine, but ``effective_fingerprint`` (dag.py:219-261) recurses once
    per dependency, so a chain deeper than the interpreter recursion limit
    raises ``RecursionError`` instead of returning a cache token.
    """
    depth = sys.getrecursionlimit() + 200
    dag, deepest = _deep_chain_dag(depth)
    assert dag.order()[-1] == deepest
    token = dag.effective_fingerprint(deepest)
    assert isinstance(token, str) and token


def test_execute_deep_dag_completes() -> None:
    """``execute`` must run a deep DAG end-to-end without RecursionError.

    ``execute`` calls ``effective_fingerprint`` for every stage, so the same
    recursion defect surfaces during execution, not just on a direct call.
    """
    depth = sys.getrecursionlimit() + 200
    dag, _deepest = _deep_chain_dag(depth)
    outputs = dag.execute()
    assert len(outputs) == depth


# -----------------------------------------------------------------------------
# concurrency.py - gather_limited return_exceptions does not honor CancelledError
# -----------------------------------------------------------------------------


def test_gather_limited_return_exceptions_collects_cancelled_subtask() -> None:
    """A cancelled subtask must be returned, not abort, in return_exceptions mode.

    ``asyncio.gather(..., return_exceptions=True)`` returns a ``CancelledError``
    as a result and keeps the other results. ``gather_limited``
    (concurrency.py:112-113) re-raises it instead, aborting the gather and
    discarding the already-completed results.
    """

    async def scenario() -> list[object]:
        async def good() -> int:
            return 1

        async def cancelled() -> None:
            raise asyncio.CancelledError()

        return await gather_limited(
            [good(), cancelled(), good()],
            limit=3,
            return_exceptions=True,
        )

    results = asyncio.run(scenario())
    assert len(results) == 3
    assert results[0] == 1
    assert isinstance(results[1], asyncio.CancelledError)
    assert results[2] == 1


# -----------------------------------------------------------------------------
# Sanity green - reference behavior that must keep working
# -----------------------------------------------------------------------------


def test_effective_fingerprint_shallow_dag_and_cacheability() -> None:
    """Sanity green: shallow DAG fingerprints are deterministic and cacheable."""
    a = WorkflowStage("a", run=lambda _d: 1, fingerprint="fa")
    b = WorkflowStage("b", run=lambda _d: 2, dependencies=("a",), fingerprint="fb")
    dag = WorkflowDAG([a, b])
    token_a = dag.effective_fingerprint("a")
    token_b = dag.effective_fingerprint("b")
    assert isinstance(token_a, str) and token_a
    assert isinstance(token_b, str) and token_b
    assert token_a != token_b
    assert dag.effective_fingerprint("b") == token_b


def test_gather_limited_return_exceptions_collects_errors() -> None:
    """Sanity green: ordinary exceptions are collected in return_exceptions mode."""

    async def scenario() -> list[object]:
        async def good() -> int:
            return 1

        async def boom() -> None:
            raise ValueError("boom")

        return await gather_limited(
            [good(), boom(), good()],
            limit=3,
            return_exceptions=True,
        )

    results = asyncio.run(scenario())
    assert results[0] == 1
    assert isinstance(results[1], ValueError)
    assert results[2] == 1


def test_gather_limited_fail_fast_propagates_by_default() -> None:
    """Sanity green: without return_exceptions, a raised error propagates."""

    async def scenario() -> None:
        async def boom() -> None:
            raise RuntimeError("boom")

        await gather_limited([boom()], limit=1)

    with pytest.raises(RuntimeError):
        asyncio.run(scenario())
