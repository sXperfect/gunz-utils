"""Perpetual security & concurrency audit - PHASE 14 (round-2) regression tests.

Round-2 re-audit of resources, result, identifiers, experiments, project, and
models. Tests are written to FAIL ("red") against the current source (base
87dd2f3, which already contains the phase 1-13 fixes) and must pass only after
the corresponding production fix lands. Production code is intentionally not
modified.

Findings covered here (NEW, not previously flagged):
1. ``compare_numeric_metrics`` (experiments.py:164-177) computes the integer
   path's ``relative_delta`` as ``delta / abs(left)`` with no overflow guard.
   For a large finite ``int`` metric the float division raises
   ``OverflowError: integer division result too large for a float`` (e.g.
   baseline ``1``, candidate ``10**400``). In ``run_variant_matrix``
   (:95) this runs outside the per-variant try/except, so it crashes the whole
   matrix instead of producing a comparison. The float path already maps huge
   ints to ``inf`` via ``_as_float``, so the int path is inconsistent.
2. ``ResourceGroup.enter`` (resources.py:22-37) and
   ``AsyncResourceGroup.enter`` (:55-70) silently enter a resource into the
   underlying ``ExitStack``/``AsyncExitStack`` even when the group's context
   manager was never entered. Unlike the standard library stack (which exposes
   ``close()``), these wrappers provide no ``close()`` and no guard, so the
   entered resource is never released: file descriptors, locks, and other
   resources leak with no recovery.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.experiments import compare_numeric_metrics, run_variant_matrix
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup


class _Closable:
    """Minimal context-manager resource tracking whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> _Closable:
        return self

    def __exit__(self, *exc: object) -> bool:
        self.closed = True
        return False


class _AsyncClosable:
    """Async context-manager resource tracking whether it was closed."""

    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> _AsyncClosable:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        self.closed = True
        return False


# -----------------------------------------------------------------------------
# experiments.py - int-path relative_delta overflows on huge finite ints
# -----------------------------------------------------------------------------


def test_compare_numeric_metrics_huge_int_delta_no_overflow() -> None:
    """A large finite int delta must not raise OverflowError.

    The int path (experiments.py:172-176) computes
    ``relative_delta = delta / abs(left)``. When ``abs(left)`` is small and the
    delta is astronomically large, Python's int/int division raises
    ``OverflowError`` ("integer division result too large for a float"), so the
    whole comparison crashes instead of returning a result (the float path maps
    such ints to ``inf`` via ``_as_float``).
    """
    result = compare_numeric_metrics({"count": 1}, {"count": 10**400})
    assert result["count"]["numeric"] is True


def test_run_variant_matrix_huge_int_metric_no_crash() -> None:
    """A huge finite int metric must not crash the entire variant matrix.

    ``run_variant_matrix`` calls ``compare_numeric_metrics`` (:95) outside the
    per-variant try/except, so the OverflowError propagates and aborts the whole
    matrix rather than being contained to one variant.
    """

    def setup() -> object:
        return object()

    def run(state: object, config: dict[str, object]) -> dict[str, object]:
        return {"count": config["count"]}

    matrix = run_variant_matrix(
        setup,
        run,
        {"baseline": {"count": 1}, "candidate": {"count": 10**400}},
    )
    assert "candidate" in matrix["comparisons"]


# -----------------------------------------------------------------------------
# resources.py - enter() on an un-entered group silently leaks
# -----------------------------------------------------------------------------


def test_resource_group_enter_without_entering_raises() -> None:
    """Entering a resource into an un-entered group must not silently leak.

    ``ResourceGroup.enter`` (:37) pushes the resource onto an ``ExitStack``
    that is only drained by ``__exit__``. Because the wrapper provides no
    ``close()`` and no entered-state guard, calling ``enter`` without entering
    the context manager leaves the resource open forever (no error, no
    cleanup), unlike the standard library ``ExitStack`` which exposes
    ``close()``.
    """
    group = ResourceGroup()
    with pytest.raises(RuntimeError):
        group.enter(_Closable())


def test_async_resource_group_enter_without_entering_raises() -> None:
    """The async group must also reject entering before it is entered."""
    group = AsyncResourceGroup()

    async def attempt() -> None:
        await group.enter(_AsyncClosable())

    with pytest.raises(RuntimeError):
        _run_async(attempt())


def _run_async(coro: object) -> None:
    import asyncio

    asyncio.run(coro)  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# Sanity green - normal usage still works
# -----------------------------------------------------------------------------


def test_compare_numeric_metrics_moderate_ints_ok() -> None:
    """Sanity green: moderate int comparisons still produce deltas."""
    result = compare_numeric_metrics({"a": 10}, {"a": 20})
    assert result["a"]["relative_delta"] == 1.0


def test_resource_group_normal_use_closes() -> None:
    """Sanity green: normal ``with``-block usage still releases resources."""
    resource = _Closable()
    with ResourceGroup() as group:
        group.enter(resource)
    assert resource.closed is True
