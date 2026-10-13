"""Perpetual correctness & performance audit regressions (phase 15).

Each test pins a defect found during the round-3 (deepest) re-audit of
``dict_utils``, ``structures``, ``streaming``, and ``sampling``. The tests
currently FAIL against the audited revision (b4ca9e9, which includes the
phase-1..14 fixes); they encode the expected post-fix behavior and should
pass once the implementation is corrected. Production code is intentionally
left untouched.
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

from gunz_utils.structures import deep_diff

# ---------------------------------------------------------------------------
# structures.deep_diff: a genuine difference at a later path is silently
# omitted when the same (left, right) object pair appears at multiple paths
# (shared, non-cyclic substructure).
#
# ``deep_diff`` (structures.py) keeps a ``visited`` set of ``(id(left),
# id(right))`` pairs intended to stop traversal on *cycles*. Because the same
# pair is never re-walked, a pair that is shared across two sibling paths is
# only compared once -- at the first path -- so a real difference at the
# second path is never reported. Example:
#   x = {"k": 1}; y = {"k": 2}
#   deep_diff({"a": x, "b": x}, {"a": y, "b": y})
# reports only the "a.k" value difference and silently misses the equally
# real "b.k" difference (with distinct objects both are reported). The cycle
# guard must not suppress legitimate repeated comparisons of shared,
# non-cyclic substructure. Expected: every path where a difference occurs is
# reported.
# ---------------------------------------------------------------------------


def test_deep_diff_reports_difference_at_every_shared_mapping_path() -> None:
    x = {"k": 1}
    y = {"k": 2}
    diffs = deep_diff({"a": x, "b": x}, {"a": y, "b": y})
    paths = {d.path for d in diffs}
    assert "a.k" in paths
    assert "b.k" in paths, (
        "deep_diff missed the difference at shared path 'b.k' "
        f"(reported paths: {sorted(paths)})"
    )


def test_deep_diff_reports_difference_at_every_shared_sequence_path() -> None:
    x = [1]
    y = [2]
    diffs = deep_diff([x, x], [y, y])
    paths = {d.path for d in diffs}
    assert "[0][0]" in paths
    assert "[1][0]" in paths, (
        "deep_diff missed the difference at shared sequence path '[1][0]' "
        f"(reported paths: {sorted(paths)})"
    )
