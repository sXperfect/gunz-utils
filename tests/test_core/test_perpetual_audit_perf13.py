"""Perpetual correctness & performance audit regressions (phase 13).

Each test pins a defect found during the round-2 re-audit of
``binary``, ``partitions``, ``signals``, ``testing``, ``testkit``, and
``identifiers``. The tests currently FAIL against the audited revision
(736a07a, which includes the phase-1..12 fixes); they encode the expected
post-fix behavior and should pass once the implementation is corrected.
Production code is intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.binary import ByteReader
from gunz_utils.signals import GracefulShutdown
from gunz_utils.testing import eventually
from gunz_utils.testkit import ManualClock, fuzz_floats

# ---------------------------------------------------------------------------
# testkit.fuzz_floats: with a wide but finite range the generator yields
# ``inf`` (and occasionally ``nan``) even when ``allow_infinity=False``,
# violating both the requested [minimum, maximum] window and the "no special
# values unless allowed" contract.
#
# fuzz_floats (testkit.py) draws from ``random.uniform(min_f, max_f)``, which
# CPython implements as ``a + (b - a) * random()``. For a wide span such as
# ``minimum=-1e308, maximum=1e308`` the subtraction ``b - a`` overflows to
# ``inf``, so every sample becomes ``inf`` (or ``nan`` when the random factor
# is exactly 0.0). The docstring promises values within ``[minimum, maximum]``
# and special values only when ``allow_nan``/``allow_infinity`` are set.
# Expected: a finite range must never yield inf/nan when those flags are off.
# ---------------------------------------------------------------------------


def test_fuzz_floats_wide_finite_range_never_yields_special_values() -> None:
    for sample in fuzz_floats(
        seed=7,
        count=500,
        minimum=-1e308,
        maximum=1e308,
    ):
        assert not math.isinf(sample) and not math.isnan(sample), (
            f"fuzz_floats produced special value {sample!r} with "
            "allow_infinity=False"
        )
        assert -1e308 <= sample <= 1e308


# ---------------------------------------------------------------------------
# binary.ByteReader: a valid non-contiguous memoryview input raises an
# internal ``TypeError`` from ``memoryview.cast`` instead of being accepted.
#
# ByteReader.__init__ (binary.py) does ``memoryview(data).cast("B")`` on its
# ``bytes | bytearray | memoryview`` input. ``cast`` requires a C-contiguous
# view, so a valid non-contiguous slice (e.g. ``memoryview(b"abcdef")[::2]``)
# raises ``TypeError: memoryview: casts are restricted to C-contiguous views``.
# This mirrors the defect previously fixed in ``buffers.as_readonly_view``
# (phase 11), but was missed here. Expected: ByteReader accepts any valid
# memoryview input, copying when necessary, so reading yields the logical
# bytes.
# ---------------------------------------------------------------------------


def test_bytereader_accepts_non_contiguous_memoryview() -> None:
    reader = ByteReader(memoryview(b"abcdef")[::2])
    assert reader.remaining == 3
    assert bytes(reader.read(3)) == b"ace"


# ---------------------------------------------------------------------------
# Unguarded float() conversions in validation paths leak ``OverflowError``
# (``int too large to convert to float``) instead of the documented
# ``ValueError`` for an integer too large to represent as a float (e.g.
# ``10**400``). This is the same defect class already fixed for
# ``async_utils.with_timeout`` in phase 12, but it was missed in these
# sibling validators. Each function documents a ``ValueError`` contract, and
# the sibling ``time_utils.monotonic_deadline`` guards ``float()`` with
# ``try/except OverflowError`` -> ValueError. Expected: these validators
# raise ValueError, never leak OverflowError.
# ---------------------------------------------------------------------------


def test_fuzz_floats_huge_integer_bounds_raise_valueerror() -> None:
    for kwarg in ({"minimum": 10**400}, {"maximum": 10**400}):
        try:
            list(fuzz_floats(seed=1, count=1, **kwarg))
        except ValueError:
            continue
        raise AssertionError(
            f"fuzz_floats({kwarg}) should raise ValueError, not OverflowError"
        )


def test_eventually_huge_timeout_raises_valueerror() -> None:
    try:
        eventually(lambda: True, timeout=10**400)
    except ValueError:
        return
    raise AssertionError("eventually(timeout=10**400) should raise ValueError")


def test_graceful_shutdown_huge_timeout_raises_valueerror() -> None:
    try:
        GracefulShutdown(timeout=10**400)
    except ValueError:
        return
    raise AssertionError(
        "GracefulShutdown(timeout=10**400) should raise ValueError"
    )


def test_manual_clock_huge_advance_raises_valueerror() -> None:
    clock = ManualClock()
    try:
        clock.advance(10**400)
    except ValueError:
        return
    raise AssertionError("ManualClock.advance(10**400) should raise ValueError")
