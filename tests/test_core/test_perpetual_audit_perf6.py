"""Perpetual correctness & performance audit regressions (phase 6).

Each test pins a defect found during the round-6 audit of
``gunz_utils.{cache,collections,iteration,limits,structures}``. The tests
currently FAIL against the audited revision (c1133b9, which includes the
phase-1..5 fixes); they encode the expected post-fix behavior and should be
un-skipped once the implementation is corrected. Production code is
intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.iteration import flatten

# ---------------------------------------------------------------------------
# flatten: a top-level scalar iterable (str/dict/set) is split into its
# elements instead of being yielded as a single leaf.
#
# ``flatten``'s docstring promises that strings, dicts, and sets are "yielded
# as-is" / "NOT descended into by default" (the ``types`` tuple defaults to
# ``(list, tuple)``), and that ``max_depth=0`` "yields each top-level element
# verbatim without descending at all". The top-level dispatch, however,
# iterates ANY iterable input directly (iteration.py ``flatten``), so a
# top-level ``str`` is split into characters, a top-level ``dict`` into its
# keys, and a top-level ``set`` into its members. This is inconsistent with
# nested handling — ``flatten(["abc"])`` yields ``["abc"]`` while
# ``flatten("abc")`` yields ``["a", "b", "c"]`` — and with the scalar fallback
# for non-iterables (``flatten(5)`` yields ``[5]``).
#
# Expected: a top-level input that is not one of ``types`` should be yielded
# as a single leaf (like the nested/scalar handling), not iterated.
# ---------------------------------------------------------------------------


def test_flatten_top_level_string_is_a_single_leaf() -> None:
    assert list(flatten("abc")) == ["abc"]


def test_flatten_top_level_string_max_depth_zero_kept_verbatim() -> None:
    assert list(flatten("ab", max_depth=0)) == ["ab"]


def test_flatten_top_level_dict_is_a_single_leaf() -> None:
    source = {"a": 1}
    assert list(flatten(source)) == [source]


def test_flatten_top_level_set_is_a_single_leaf() -> None:
    source = {1, 2, 3}
    assert list(flatten(source)) == [source]


def test_flatten_nested_string_remains_leaf_consistent() -> None:
    # Nested strings are already treated as scalar leaves; the top-level
    # string should behave identically rather than being split into chars.
    assert list(flatten(["abc"])) == ["abc"]
    assert list(flatten("abc")) == ["abc"]
