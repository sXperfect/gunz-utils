"""Phase 25 perpetual audit: round-4 (deepest) re-audit of structures/enums/iteration.

iteration.py (chunked/batched/flatten/first) and enums.py
(from_fuzzy_string/from_fuzzy_int_string/get_or_none/aliases/name-value
collision/bool rejection) were verified correct across fuzz and targeted probes.
structures.py deep_diff/freeze_structure/RingBuffer/top_k/retain_priority_and_recent
were fuzzed (deep_diff(A,A)==[] and flatten-vs-reference hold over 30k cases;
freeze_structure handles shared and cyclic graphs). One NEW bug surfaced in
deep_diff's scalar-leaf comparison: a strict type-identity pre-check reports a
"type" difference for numerically-equal values of different numeric types,
contradicting the documented scalar-boolean-equality leaf contract.

This test is expected to be RED against base ``af0cd2e`` and documents the
correct behavior after a fix.
"""

from __future__ import annotations

from decimal import Decimal

from gunz_utils.structures import deep_diff


# ---------------------------------------------------------------------------
# structures.deep_diff reports a "type" difference for numerically-equal leaf
# values, contradicting the documented scalar boolean-equality contract.
#
# The docstring (structures.py:239-242) states "Leaf values should implement
# scalar boolean equality", and the function's purpose is to report DIFFERENCES.
# But the scalar-leaf branch (structures.py:380-389) first checks
# ``type(left_value) is type(right_value)`` and reports a "type" difference
# before ever testing equality. As a result two values that are equal under
# scalar boolean equality (``1 == 1.0`` is True) are reported as different:
#   deep_diff({"x": 1}, {"x": 1.0}) -> [DeepDifference(path='x', kind='type', ...)]
# This is a false positive for a configuration/manifest/metadata diff tool: the
# values are equal, so no difference should be reported. It affects every
# numeric pair that is equal but of different numeric types (int vs float,
# int vs Decimal, int vs Fraction, bool vs int, ...).
# ---------------------------------------------------------------------------
def test_deep_diff_numeric_equal_values_not_reported_as_difference() -> None:
    assert deep_diff({"x": 1}, {"x": 1.0}) == []
    assert deep_diff({"x": 2}, {"x": 2.0}) == []
    assert deep_diff({"x": 1}, {"x": Decimal("1")}) == []


def test_deep_diff_numeric_equal_nested_not_reported_as_difference() -> None:
    assert deep_diff({"a": {"b": [3]}}, {"a": {"b": [3.0]}}) == []
