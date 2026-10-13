"""Perpetual security & concurrency audit - PHASE 21 (round-3) regression tests.

Round-3 re-audit of models, pipeline, experiments, and resources (the deepest
deferred/NEW issues two prior passes missed). Tests are written to FAIL ("red")
against the current source (base e2c541a, which already contains the phase 1-20
fixes) and must pass only after the corresponding production fix lands.
Production code is intentionally not modified.

Findings covered here (NEW, not previously flagged):

1. ``GunzBaseModel._reject_bool_for_int_fields`` (models.py:108-126, via
   ``_annotation_is_int`` models.py:38-64) wrongly rejects a legitimate
   ``bool`` for a field explicitly annotated as ``int | bool`` (or
   ``int | bool | None``). ``_annotation_is_int`` treats a union as int-typed
   with ``any(...)`` over its members, so the presence of the ``int`` member
   makes ``int | bool`` look int-only and the guard raises
   ``ValueError("field 'x' must be an int, got bool")`` even though the field
   declares that bool is acceptable. Only unions with no ``bool`` member should
   be treated as int-only.

2. ``ResourceGroup.enter`` (resources.py:24-47) and ``AsyncResourceGroup.enter``
   raise ``RuntimeError`` only when the group was never entered, because the
   ``_entered`` flag is set in ``__enter__`` but never reset in ``__exit__`` /
   ``__aexit__`` (resources.py:49-54, 92-97). After the ``with`` block ends,
   ``enter()`` silently pushes a resource onto an already-exited stack that can
   never release it - exactly the silent leak the guard's own docstring claims
   to prevent.

3. ``compare_numeric_metrics`` (experiments.py:164-187) crashes with
   ``OverflowError`` when the baseline (or candidate) is an ``int`` too large
   to convert to ``float`` (e.g. ``10**400``). The overflow-safe conversion
   covers only the delta numerator (``_as_float(delta)``), but the very next
   division ``_as_float(delta) / abs(left)`` converts the huge int denominator
   ``abs(left)`` to ``float``, raising ``OverflowError`` instead of reporting a
   non-finite relative delta as ``None``.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import math
import os

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.experiments import compare_numeric_metrics
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup

# -----------------------------------------------------------------------------
# models.py - bool rejected for int | bool (and int | bool | None) fields
# -----------------------------------------------------------------------------


def test_models_int_bool_union_accepts_bool() -> None:
    """RED: a bool is a valid value for an int | bool field."""
    pytest.importorskip("pydantic")
    from gunz_utils.models import GunzBaseModel

    class M(GunzBaseModel):
        x: int | bool

    result = M(x=True)
    assert result.x is True


def test_models_int_bool_none_union_accepts_bool() -> None:
    """RED: a bool is a valid value for an int | bool | None field."""
    pytest.importorskip("pydantic")
    from gunz_utils.models import GunzBaseModel

    class N(GunzBaseModel):
        y: int | bool | None

    result = N(y=False)
    assert result.y is False


def test_models_int_field_still_rejects_bool() -> None:
    """Sanity green: a plain int field still rejects a bool."""
    pytest.importorskip("pydantic")
    from gunz_utils.models import GunzBaseModel

    class M(GunzBaseModel):
        x: int

    with pytest.raises(ValueError):
        M(x=True)


# -----------------------------------------------------------------------------
# resources.py - enter() after the context has exited must raise, not leak
# -----------------------------------------------------------------------------


def test_resource_group_enter_after_exit_raises() -> None:
    """RED: pushing a resource after the group exited must not silently leak."""
    group = ResourceGroup()
    with group:
        group.enter(open(os.devnull, "w"))
    with pytest.raises(RuntimeError):
        group.enter(open(os.devnull, "w"))


def test_async_resource_group_enter_after_exit_raises() -> None:
    """RED: async variant must also refuse enter() after exit."""
    import asyncio
    import contextlib

    @contextlib.asynccontextmanager
    async def open_resource() -> object:
        #? Stand-in for an async openable resource. ``asyncio.open`` does not
        #? exist in Python, so the original reference could not execute; this
        #? preserves the test's intent (enter inside the context works, enter
        #? after exit raises).
        yield object()

    async def scenario() -> None:
        group = AsyncResourceGroup()
        async with group:
            await group.enter(open_resource())
        with pytest.raises(RuntimeError):
            await group.enter(open_resource())

    asyncio.run(scenario())


def test_resource_group_enter_before_enter_raises() -> None:
    """Sanity green: enter() before entering the context still raises."""
    group = ResourceGroup()
    with pytest.raises(RuntimeError):
        group.enter(open(os.devnull, "w"))


def test_resource_group_enter_inside_context_works() -> None:
    """Sanity green: enter() inside the context still returns the resource."""
    group = ResourceGroup()
    with group:
        handle = group.enter(open(os.devnull, "w"))
        assert handle is not None


# -----------------------------------------------------------------------------
# experiments.py - compare_numeric_metrics must not crash on huge int metrics
# -----------------------------------------------------------------------------


def test_compare_numeric_metrics_huge_int_baseline_no_crash() -> None:
    """RED: a huge int baseline must not raise OverflowError."""
    huge = 10**400
    result = compare_numeric_metrics({"m": huge}, {"m": huge + 1})
    entry = result["m"]
    assert entry["numeric"] is True
    assert entry["relative_delta"] is None or math.isfinite(entry["relative_delta"])


def test_compare_numeric_metrics_normal_ints() -> None:
    """Sanity green: ordinary int metrics still compare correctly."""
    result = compare_numeric_metrics({"m": 10}, {"m": 15})
    entry = result["m"]
    assert entry["numeric"] is True
    assert entry["delta"] == 5
    assert entry["relative_delta"] == 0.5
