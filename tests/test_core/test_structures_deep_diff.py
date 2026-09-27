"""Tests for typed deep structural differences."""

from __future__ import annotations

from gunz_utils.structures import DeepDifference, deep_diff


def test_deep_diff_reports_nested_value_and_missing_keys() -> None:
    result = deep_diff(
        {
            "model": {
                "depth": 12,
                "dropout": None,
            },
            "left_only": 1,
        },
        {
            "model": {
                "depth": 16,
                "dropout": None,
            },
            "right_only": 2,
        },
    )

    assert result == [
        DeepDifference(
            "left_only",
            "missing_right",
            1,
            None,
        ),
        DeepDifference(
            "model.depth",
            "value",
            12,
            16,
        ),
        DeepDifference(
            "right_only",
            "missing_left",
            None,
            2,
        ),
    ]


def test_deep_diff_distinguishes_present_none_from_missing() -> None:
    result = deep_diff(
        {"value": None},
        {},
    )

    assert result == [
        DeepDifference(
            "value",
            "missing_right",
            None,
            None,
        )
    ]


def test_deep_diff_reports_sequence_length_and_values() -> None:
    result = deep_diff(
        [1, 2, 3],
        [1, 4],
        path="items",
    )

    assert DeepDifference(
        "items",
        "length",
        3,
        2,
    ) in result
    assert DeepDifference(
        "items[1]",
        "value",
        2,
        4,
    ) in result
    assert DeepDifference(
        "items[2]",
        "missing_right",
        3,
        None,
    ) in result


def test_deep_diff_reports_sequence_type_mismatch() -> None:
    result = deep_diff(
        [1, 2],
        (1, 2),
    )

    assert result == [
        DeepDifference(
            "",
            "type",
            "list",
            "tuple",
        )
    ]


def test_deep_diff_handles_matching_cycles() -> None:
    left: list[object] = []
    right: list[object] = []
    left.append(left)
    right.append(right)

    assert deep_diff(left, right) == []
