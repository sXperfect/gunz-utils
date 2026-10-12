"""Perpetual correctness & performance audit regressions (phase 1).

Each test in this module pins a defect found during the round-1 audit of
``gunz_utils.{iteration,structures,dict_utils,formatting,limits,signals}``.
The tests currently FAIL against the audited revision; they encode the
expected post-fix behavior and should be un-skipped once the implementation
is corrected. Production code is intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.dict_utils import deep_merge
from gunz_utils.formatting import format_bytes, format_duration


# ---------------------------------------------------------------------------
# format_bytes / format_duration: negative fractional values produce a
# meaningless "-0 B" / "-0ms" string.
#
# When the magnitude of a negative fractional input truncates to zero, the
# sign prefix is still emitted, yielding "-0 B" (format_bytes) and "-0ms"
# (format_duration). A sign on a zero magnitude is meaningless and surprising
# in log/CLI output. The expected behavior is to suppress the sign whenever
# the truncated magnitude is zero, exactly like a positive zero input.
# ---------------------------------------------------------------------------


def test_format_bytes_negative_fractional_does_not_emit_minus_zero() -> None:
    # Negative fractional magnitudes that truncate to zero must not print
    # a leading minus sign on zero ("-0 B").
    assert format_bytes(-0.5) == "0 B"
    assert format_bytes(-0.0001) == "0 B"


def test_format_bytes_negative_fractional_binary_does_not_emit_minus_zero() -> None:
    assert format_bytes(-0.5, binary=True) == "0 B"


def test_format_duration_negative_subsecond_does_not_emit_minus_zero() -> None:
    # Sub-second negative durations that truncate to 0ms must not print "-0ms".
    # ``-0.001`` has magnitude exactly 1ms and is NOT a zero-truncating input
    # (it correctly renders "-1ms"), so only genuinely sub-millisecond inputs
    # that truncate to 0ms are asserted here.
    assert format_duration(-0.0001) == "0ms"
    assert format_duration(-0.0004) == "0ms"


# ---------------------------------------------------------------------------
# deep_merge(list_strategy="dedup"): boolean and integer leaves are conflated.
#
# Deduplication is implemented with a Python set, so ``True == 1`` and
# ``False == 0`` collapse into a single entry. The rest of the package is
# deliberately strict about treating ``bool`` as distinct from ``int`` (every
# numeric parameter rejects booleans), so a merge that silently drops a
# ``True`` because a ``1`` is already present is inconsistent with that
# contract and loses information. Expected behavior: dedup keeps ``bool``
# leaves distinct from equal-valued ``int`` leaves.
# ---------------------------------------------------------------------------


def test_deep_merge_dedup_keeps_bool_distinct_from_int() -> None:
    merged = deep_merge(
        {"xs": [1]},
        {"xs": [True]},
        list_strategy="dedup",
    )
    assert merged["xs"] == [1, True]


def test_deep_merge_dedup_keeps_false_distinct_from_zero() -> None:
    merged = deep_merge(
        {"xs": [0]},
        {"xs": [False]},
        list_strategy="dedup",
    )
    assert merged["xs"] == [0, False]


# ---------------------------------------------------------------------------
# deep_merge: unbounded recursion on deeply nested mappings.
#
# ``deep_merge`` recurses through nested mappings via ``_merge``/``_isolate``
# and raises an unhandled ``RecursionError`` on inputs nested beyond ~1000
# levels. ``deep_diff`` and ``freeze_structure`` in the same package were
# deliberately written iteratively to support untrusted/deep configuration
# trees, and ``deep_get`` walks iteratively — ``deep_merge`` is the odd one
# out. Expected behavior: merging a deeply nested mapping must not raise
# ``RecursionError``; it should either complete iteratively or raise a clear,
# controlled ``ValueError`` about depth (never an unbounded interpreter
# recursion failure).
# ---------------------------------------------------------------------------


def test_deep_merge_does_not_recurse_unboundedly_on_deep_input() -> None:
    depth = 1500

    def deep_dict(n: int) -> dict:
        root: dict = {}
        cursor = root
        for _ in range(n):
            nxt: dict = {}
            cursor["k"] = nxt
            cursor = nxt
        return root

    try:
        result = deep_merge(deep_dict(depth), {"extra": 1})
    except RecursionError:
        # ``from None`` avoids pytest formatting the enormous RecursionError
        # traceback, which dominates the test's runtime. The assertion below
        # is the regression contract.
        raise AssertionError(
            "deep_merge raised RecursionError on deeply nested input; "
            "it must handle deep config trees without unbounded recursion"
        ) from None

    assert isinstance(result, dict)
    assert result["extra"] == 1
