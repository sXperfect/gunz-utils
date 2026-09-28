"""Method-level proof tests for high-risk algorithm families."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

import pytest

from gunz_utils.binary import ByteReader, encode_uvarint
from gunz_utils.dag import WorkflowDAG, WorkflowStage


def _reference_acyclic(
    names: tuple[str, ...],
    edges: Iterable[tuple[str, str]],
) -> bool:
    outgoing = {name: [] for name in names}
    indegree = {name: 0 for name in names}
    for source, target in edges:
        outgoing[source].append(target)
        indegree[target] += 1

    ready = deque(name for name in names if indegree[name] == 0)
    visited = 0
    while ready:
        source = ready.popleft()
        visited += 1
        for target in outgoing[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    return visited == len(names)


def test_workflow_dag_matches_exhaustive_four_node_cycle_oracle() -> None:
    names = ("a", "b", "c", "d")
    possible_edges = tuple(
        (source, target)
        for source in names
        for target in names
        if source != target
    )

    for mask in range(1 << len(possible_edges)):
        edges = tuple(
            edge
            for index, edge in enumerate(possible_edges)
            if mask & (1 << index)
        )
        dependencies = {name: [] for name in names}
        for source, target in edges:
            dependencies[target].append(source)

        stages = [
            WorkflowStage(
                name,
                lambda _values: None,
                tuple(dependencies[name]),
            )
            for name in names
        ]

        if not _reference_acyclic(names, edges):
            with pytest.raises(ValueError, match="cycle"):
                WorkflowDAG(stages)
            continue

        order = WorkflowDAG(stages).order()
        positions = {name: index for index, name in enumerate(order)}
        assert set(order) == set(names)
        assert len(order) == len(names)
        for source, target in edges:
            assert positions[source] < positions[target]


def _reference_uvarint(value: int) -> bytes:
    output = bytearray()
    remaining = value
    while remaining >= 128:
        quotient, remainder = divmod(remaining, 128)
        output.append(remainder | 0x80)
        remaining = quotient
    output.append(remaining)
    return bytes(output)


def test_uvarint_exhaustive_small_domain_matches_reference() -> None:
    for value in range(1 << 16):
        encoded = encode_uvarint(value)
        assert encoded == _reference_uvarint(value)

        reader = ByteReader(encoded)
        assert reader.read_uvarint() == value
        assert reader.remaining == 0

        expected_length = 1 if value == 0 else (value.bit_length() + 6) // 7
        assert len(encoded) == expected_length


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        127,
        128,
        255,
        16_383,
        16_384,
        2**32 - 1,
        2**63 - 1,
        2**64 - 1,
    ],
)
def test_uvarint_uint64_boundaries(value: int) -> None:
    encoded = encode_uvarint(value)
    assert encoded == _reference_uvarint(value)
    assert ByteReader(encoded).read_uvarint() == value


@pytest.mark.parametrize(
    "payload",
    [
        b"\x80",
        b"\x80\x00",
        b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\x02",
        b"\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80",
    ],
)
def test_uvarint_malformed_input_rolls_back_reader(payload: bytes) -> None:
    reader = ByteReader(payload)
    with pytest.raises((EOFError, ValueError)):
        reader.read_uvarint()
    assert reader.offset == 0
