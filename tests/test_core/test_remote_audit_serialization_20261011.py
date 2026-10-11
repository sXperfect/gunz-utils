"""Strict subclass and canonical set proofs plus supported copy-alias limits."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import IntEnum
from typing import Any

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils import binary, serialization
from gunz_utils.dict_utils import deep_merge


class _ArithmeticInteger(int):
    def __and__(self,
        other: int,
    ) -> int:
        return 7


class _ComparisonInteger(int):
    def __lt__(self,
        other: object,
    ) -> bool:
        return True


class _Code(IntEnum):
    VALUE = 129


class _HashableMapping(Mapping[str, int]):
    def __init__(self,
        entries: list[tuple[str, int]],
    ) -> None:
        self.entries = dict(entries)

    def __getitem__(self,
        key: str,
    ) -> int:
        return self.entries[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def __hash__(self) -> int:
        return hash(frozenset(self.entries.items()))


@pytest.mark.parametrize(
    "value", [_ArithmeticInteger(129), _ComparisonInteger(3), _Code.VALUE]
)
def test_supported_integer_subclasses_match_reference(
    value: int,
) -> None:
    try:
        expected = binary._py_encode_uvarint(value)
    except ValueError as error:
        with pytest.raises(ValueError, match=str(error)):
            binary.encode_uvarint(value)
    else:
        assert binary.encode_uvarint(value) == expected


@pytest.mark.parametrize("value", [True, False, 1.5, "1", None])
def test_noninteger_or_boolean_varint_inputs_remain_rejected(
    value: Any,
) -> None:
    with pytest.raises(TypeError, match="integer"):
        binary.encode_uvarint(value)


@pytest.mark.parametrize("container", [set, frozenset])
def test_equal_mapping_sets_have_stable_canonical_order(
    container: Any,
) -> None:
    first = _HashableMapping([("a", 1), ("z", 9)])
    reordered = _HashableMapping([("z", 9), ("a", 1)])
    other = _HashableMapping([("m", 5)])
    assert first == reordered
    assert serialization.canonical_json(container([first, other])) == (
        serialization.canonical_json(container([reordered, other]))
    )
    assert serialization.json_loads(
        serialization.canonical_json(container([first, other]))
    ) == [{"a": 1, "z": 9}, {"m": 5}]


def test_set_passthrough_objects_are_not_converted_by_sort_key() -> None:
    value = object()
    converted = serialization.to_jsonable({value})
    assert converted == [value]
    assert converted[0] is value
    with pytest.raises(TypeError):
        serialization.canonical_json({value})


def test_uncopyable_mutable_leaf_has_explicit_supported_aliasing_limit() -> None:
    class Uncopyable:
        def __init__(self) -> None:
            self.values = [1]

        def __deepcopy__(self,
            memo: object,
        ) -> object:
            raise TypeError("synthetic uncopyable leaf")

    leaf = Uncopyable()
    original = {"subtree": {"copied": [1], "leaf": leaf}}
    result = deep_merge(original, {})
    assert result["subtree"] is not original["subtree"]
    assert result["subtree"]["leaf"] is leaf
    result["subtree"]["copied"].append(2)
    assert original["subtree"]["copied"] == [1]
    result["subtree"]["leaf"].values.append(2)
    assert leaf.values == [1, 2]
