"""Perpetual correctness & performance audit regressions (phase 11).

Each test pins a defect found during the round-2 re-audit of
``iteration`` and ``buffers`` (and related modules). The tests currently
FAIL against the audited revision (531641e, which includes the phase-1..10
fixes); they encode the expected post-fix behavior and should pass once the
implementation is corrected. Production code is intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.buffers import as_readonly_view
from gunz_utils.iteration import flatten

# ---------------------------------------------------------------------------
# iteration.flatten: a generator nested inside a list/tuple is yielded as an
# opaque leaf, while the same generator at the top level is consumed and its
# items walked. This asymmetry means ``flatten`` is not consistent about how
# it treats non-leaf iterables.
#
# The top-level dispatch (iteration.py) explicitly consumes generators: the
# "Generators and other non-leaf iterables are consumed and their items
# walked" branch iterates a top-level generator and walks each element. But
# ``_walk`` (iteration.py) only descends into containers matching ``types``
# (list/tuple) and yields everything else -- including a generator -- as a
# single leaf. So ``flatten(gen())`` yields ``[1, 2]`` while
# ``flatten([gen()])`` yields the generator object itself. Expected: nested
# generators are consumed and flattened just like top-level ones.
# ---------------------------------------------------------------------------


def test_flatten_consumes_nested_generators_like_top_level() -> None:
    def source() -> None:
        yield 1
        yield 2

    assert list(flatten([source(), [3]])) == [1, 2, 3]


def test_flatten_consumes_generator_inside_tuple() -> None:
    def source() -> None:
        yield 1
        yield 2

    assert list(flatten((source(),))) == [1, 2]


# ---------------------------------------------------------------------------
# buffers.as_readonly_view: a non-contiguous memoryview slice raises an
# internal ``TypeError`` from ``memoryview.cast`` instead of returning a
# byte-oriented readonly view.
#
# ``as_readonly_view`` (buffers.py) accepts ``bytes | bytearray | memoryview``
# and does ``memoryview(data).cast("B").toreadonly()``. ``cast`` requires a
# C-contiguous view, so a valid non-contiguous ``memoryview`` slice (e.g.
# ``memoryview(b"abcdef")[::2]``) raises ``TypeError: memoryview: casts are
# restricted to C-contiguous views``. The docstring promises "without copying
# when possible", implying a copy is made when a zero-copy byte view is not
# available -- not an internal error. Expected: ``as_readonly_view`` returns a
# readonly byte view for any accepted input, copying when necessary so a
# non-contiguous slice yields its logical bytes.
# ---------------------------------------------------------------------------


def test_as_readonly_view_handles_non_contiguous_memoryview() -> None:
    view = as_readonly_view(memoryview(b"abcdef")[::2])
    assert view.readonly
    assert bytes(view) == b"ace"
