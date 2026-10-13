"""Perpetual correctness & performance audit regressions (phase 7).

Each test pins a defect found during the round-7 audit of
``gunz_utils.{typed_config,diagnostics,instrumentation,testing,testkit}``.
The tests currently FAIL against the audited revision (100d3a6, which
includes the phase-1..6 fixes); they encode the expected post-fix behavior
and should pass once the implementation is corrected. Production code is
intentionally left untouched.
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

from gunz_utils.instrumentation import Counter, Trace
from gunz_utils.typed_config import parse_bool

# ---------------------------------------------------------------------------
# instrumentation.Counter.add: the amount is not validated, so a float or bool
# silently corrupts the counter's documented ``int`` value.
#
# ``Counter.value`` is typed ``int`` and every other numeric API in the
# package (Limits, ResourceBudget, ManualClock, the audit's phase-1..5
# helpers) explicitly rejects bool and non-int amounts. ``Counter.add``
# instead performs ``self.value += amount`` unconditionally, so ``add(1.5)``
# turns the integer counter into a float and ``add(True)`` silently counts a
# boolean as 1. Expected: reject a non-``int`` (including ``bool``) amount
# with ``ValueError``, preserving the integer counter invariant.
# ---------------------------------------------------------------------------


def test_counter_add_rejects_bool_amount() -> None:
    with pytest.raises(ValueError):
        Counter().add(True)


def test_counter_add_rejects_float_amount() -> None:
    with pytest.raises(ValueError):
        Counter().add(1.5)


# ---------------------------------------------------------------------------
# instrumentation.Trace.slowest: ``n`` is not validated as an integer.
#
# ``slowest`` documents "Raises ValueError if n is negative" but performs no
# type check. ``slowest(1.5)`` and ``slowest("x")`` leak a raw ``TypeError``
# from the list slice, and ``slowest(True)`` silently truncates to ``[:1]``
# (bool accepted as the integer 1). Expected: reject a non-``int`` (including
# ``bool``) ``n`` with ``ValueError``, matching the documented error contract
# and the package's bool/int validation convention.
# ---------------------------------------------------------------------------


def test_trace_slowest_rejects_bool_n() -> None:
    trace = Trace()
    with trace.span("a"):
        pass
    with pytest.raises(ValueError):
        trace.slowest(True)


def test_trace_slowest_rejects_non_int_n() -> None:
    trace = Trace()
    with trace.span("a"):
        pass
    with pytest.raises(ValueError):
        trace.slowest(1.5)


# ---------------------------------------------------------------------------
# typed_config.parse_bool: a non-string input (including a Python bool) leaks
# an internal ``AttributeError`` instead of a clean validation error.
#
# ``parse_bool`` is the config bool parser; its signature is ``str`` but it
# never validates its input before calling ``value.strip()``. Passing ``True``
# (a ``bool``, which is trivially easy to confuse with the string form) or an
# ``int`` such as ``1`` raises ``AttributeError: 'bool' object has no
# attribute 'strip'``. Expected: reject a non-``str`` input with a clean
# ``ValueError``/``TypeError`` (never leak ``AttributeError``), which is the
# bool-vs-int / type separation the package enforces elsewhere.
# ---------------------------------------------------------------------------


def test_parse_bool_rejects_bool_input() -> None:
    with pytest.raises((ValueError, TypeError)):
        parse_bool(True)


def test_parse_bool_rejects_int_input() -> None:
    with pytest.raises((ValueError, TypeError)):
        parse_bool(1)
