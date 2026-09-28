"""Tests for priority-aware bounded retention."""

from __future__ import annotations

import pytest

from gunz_utils.structures import retain_priority_and_recent


def test_retain_priority_and_recent_preserves_order() -> None:
    items = [
        ("normal", 0),
        ("priority", 1),
        ("normal", 2),
        ("priority", 3),
        ("normal", 4),
    ]

    retained = retain_priority_and_recent(
        items,
        is_priority=lambda item: item[0] == "priority",
        max_recent=1,
    )

    assert retained == [
        ("priority", 1),
        ("priority", 3),
        ("normal", 4),
    ]


def test_retain_priority_and_recent_zero_keeps_only_priority() -> None:
    retained = retain_priority_and_recent(
        [1, 2, 3, 4],
        is_priority=lambda value: value % 2 == 0,
        max_recent=0,
    )

    assert retained == [2, 4]


def test_retain_priority_and_recent_none_disables_pruning() -> None:
    values = [1, 2, 3]

    assert retain_priority_and_recent(
        values,
        is_priority=lambda _value: False,
        max_recent=None,
    ) == values


def test_retain_priority_and_recent_rejects_negative_limit() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        retain_priority_and_recent(
            [1],
            is_priority=lambda _value: False,
            max_recent=-1,
        )



def test_retain_priority_predicate_is_evaluated_once_per_item() -> None:
    calls: dict[int, int] = {}

    def priority(value: int) -> bool:
        calls[value] = calls.get(value, 0) + 1
        return value == 2

    retained = retain_priority_and_recent(
        [1, 2, 3],
        is_priority=priority,
        max_recent=1,
    )

    assert retained == [2, 3]
    assert calls == {
        1: 1,
        2: 1,
        3: 1,
    }


def test_retain_priority_and_recent_rejects_boolean_limit() -> None:
    with pytest.raises(ValueError, match="max_recent"):
        retain_priority_and_recent(
            [1, 2, 3],
            is_priority=lambda _value: False,
            max_recent=True,
        )
