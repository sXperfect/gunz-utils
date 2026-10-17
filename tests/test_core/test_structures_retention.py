"""Tests for priority-aware bounded retention."""

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

from gunz_utils.structures import (
    RingBuffer,
    retain_priority_and_recent,
    stable_unique,
    top_k,
)


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

    def priority(
        value: int,
    ) -> bool:
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


def test_top_k_returns_largest_values_and_validates_k() -> None:
    assert top_k([5, 1, 9, 3, 7], 3) == [9, 7, 5]
    assert top_k([], 5) == []
    assert top_k([1, 2, 3], 0) == []
    assert top_k([1, 2], 5) == [2, 1]
    assert top_k((x for x in range(10)), 2) == [9, 8]

    with pytest.raises(ValueError, match="non-negative integer"):
        top_k([1, 2, 3], -1)

    with pytest.raises(ValueError, match="non-negative integer"):
        top_k([1, 2, 3], True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="non-negative integer"):
        top_k([1, 2, 3], 1.5)  # type: ignore[arg-type]


def test_stable_unique_preserves_first_seen_order() -> None:
    assert list(stable_unique([3, 1, 3, 2, 1, 4])) == [3, 1, 2, 4]
    assert list(stable_unique([])) == []


def test_ring_buffer_fifo_eviction_and_boundaries() -> None:
    ring = RingBuffer[int](3)
    assert len(ring) == 0
    assert list(ring) == []

    ring.append(1)
    ring.append(2)
    assert len(ring) == 2
    assert list(ring) == [1, 2]

    ring.append(3)
    assert len(ring) == 3
    assert list(ring) == [1, 2, 3]

    #? FIFO eviction of oldest items
    ring.append(4)
    assert len(ring) == 3
    assert list(ring) == [2, 3, 4]

    ring.append(5)
    assert len(ring) == 3
    assert list(ring) == [3, 4, 5]

    #? Boundary and domain checks
    for invalid in (0, -1, True, 1.5, "3"):
        with pytest.raises(ValueError, match="capacity must be a positive integer"):
            RingBuffer[int](invalid)  # type: ignore[arg-type]

