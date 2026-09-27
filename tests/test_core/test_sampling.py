"""Tests for deterministic named-item sampling."""

from __future__ import annotations

from typing import Any, cast

import pytest

from gunz_utils.sampling import sample_named_items, stable_priority


def test_stable_priority_is_repeatable_and_seeded() -> None:
    first = stable_priority("encoder.layer.0", seed=17)
    second = stable_priority("encoder.layer.0", seed=17)
    different_seed = stable_priority("encoder.layer.0", seed=18)

    assert first == second
    assert first != different_seed
    assert 0 <= first < 2**64


def test_sample_named_items_is_input_order_independent_for_unique_names() -> None:
    items = [(f"item-{index}", index) for index in range(20)]

    forward = sample_named_items(items, limit=5, seed=23)
    reverse = sample_named_items(reversed(items), limit=5, seed=23)

    assert forward == reverse
    assert len(forward) == 5


def test_sample_named_items_filters_before_budget() -> None:
    result = sample_named_items(
        [
            ("encoder.a", 1),
            ("encoder.b", 2),
            ("decoder.a", 3),
        ],
        limit=10,
        include_patterns=("encoder.*",),
        exclude_patterns=("*.b",),
    )

    assert result == [("encoder.a", 1)]


def test_sample_named_items_none_and_zero_limits() -> None:
    items = [("a", 1), ("b", 2)]

    all_items = sample_named_items(items, limit=None)
    no_items = sample_named_items(items, limit=0)

    assert {name for name, _ in all_items} == {"a", "b"}
    assert no_items == []


def test_sample_named_items_rejects_negative_limit() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        sample_named_items([("a", 1)], limit=-1)


def test_sampling_rejects_non_string_names() -> None:
    invalid_name = cast(Any, 1)
    invalid_items = cast(Any, [(1, "value")])

    with pytest.raises(TypeError, match="name"):
        stable_priority(invalid_name)

    with pytest.raises(TypeError, match="item name"):
        sample_named_items(invalid_items, limit=1)



def test_sample_named_items_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="duplicate item name"):
        sample_named_items(
            [
                ("same", 1),
                ("same", 2),
            ],
            limit=1,
        )
