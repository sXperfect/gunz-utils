"""Tests for Wave 4 Sub-Wave 2: Buffers, Collections & Structures (#14–#26)."""
from __future__ import annotations

import pytest
from gunz_utils.buffers import ChunkedBuffer, RingBuffer as BinaryRingBuffer
from gunz_utils.collections import (
    FrozenDict,
    OrderedSet,
    chunked,
    flatten,
    group_by,
    index_by,
    partition,
    unique,
)
from gunz_utils.structures import BiMap, PriorityQueue, RingBuffer as GenericRingBuffer


# =============================================================================
# #14–#16: buffers.RingBuffer & ChunkedBuffer
# =============================================================================

def test_binary_ring_buffer_read_write_peek_discard():
    buf = BinaryRingBuffer(capacity=8)
    assert buf.capacity == 8
    assert buf.is_empty
    assert not buf.is_full
    assert len(buf) == 0

    written = buf.write(b"hello")
    assert written == 5
    assert len(buf) == 5
    assert not buf.is_empty
    assert not buf.is_full

    # Peek without advancing read pointer
    assert buf.peek(3) == b"hel"
    assert len(buf) == 5

    # Read 3 bytes
    assert buf.read(3) == b"hel"
    assert len(buf) == 2

    # Discard 1 byte
    discarded = buf.discard(1)
    assert discarded == 1
    assert len(buf) == 1

    # Read remaining
    assert buf.read(5) == b"o"
    assert buf.is_empty

    # Discard on empty
    assert buf.discard(5) == 0


def test_binary_ring_buffer_wraparound_and_full():
    buf = BinaryRingBuffer(capacity=4)
    buf.write(b"1234")
    assert buf.is_full
    assert len(buf) == 4

    # Extra write when full writes 0 bytes
    assert buf.write(b"56") == 0

    # Read 2, now 2 slots open
    assert buf.read(2) == b"12"
    assert not buf.is_full

    # Write 2 wraps around
    assert buf.write(b"AB") == 2
    assert buf.is_full
    assert bytes(buf) == b"34AB"
    assert buf.read() == b"34AB"
    assert buf.is_empty

    # Clear
    buf.write(b"test")
    buf.clear()
    assert buf.is_empty
    assert len(buf) == 0


def test_binary_ring_buffer_invalid_capacity():
    with pytest.raises(ValueError, match="positive integer"):
        BinaryRingBuffer(0)
    with pytest.raises(ValueError, match="positive integer"):
        BinaryRingBuffer(-5)
    with pytest.raises(TypeError, match="capacity must be an integer"):
        BinaryRingBuffer("10")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="capacity must be an integer"):
        BinaryRingBuffer(True)  # type: ignore[arg-type]


def test_chunked_buffer_append_and_to_bytes():
    buf = ChunkedBuffer()
    assert len(buf) == 0
    assert buf.to_bytes() == b""

    buf.append(b"hello ")
    buf.append(bytearray(b"world"))
    buf.append(memoryview(b"!"))

    assert buf.total_bytes == 12
    assert len(buf) == 12
    assert buf.to_bytes() == b"hello world!"

    buf.clear()
    assert len(buf) == 0
    assert buf.to_bytes() == b""


# =============================================================================
# #17–#21: collections.OrderedSet, FrozenDict, chunked, flatten, guards
# =============================================================================

def test_ordered_set_operations():
    s = OrderedSet(["apple", "banana", "cherry", "apple"])
    assert len(s) == 3
    assert list(s) == ["apple", "banana", "cherry"]
    assert "banana" in s
    assert "date" not in s

    s.add("date")
    assert list(s) == ["apple", "banana", "cherry", "date"]
    s.add("apple")
    assert list(s) == ["apple", "banana", "cherry", "date"]

    s.discard("banana")
    assert "banana" not in s
    assert list(s) == ["apple", "cherry", "date"]

    popped = s.pop()
    assert popped == "date"

    # Set operations
    other = OrderedSet(["cherry", "elderberry"])
    union = s | other
    assert list(union) == ["apple", "cherry", "elderberry"]

    intersection = s & other
    assert list(intersection) == ["cherry"]

    diff = s - other
    assert list(diff) == ["apple"]

    xor = s ^ other
    assert list(xor) == ["apple", "elderberry"]

    assert s == OrderedSet(["apple", "cherry"])
    assert s == {"apple", "cherry"}
    assert repr(s) == "OrderedSet(['apple', 'cherry'])"


def test_frozen_dict():
    fd = FrozenDict({"a": 1, "b": 2})
    assert fd["a"] == 1
    assert fd["b"] == 2
    assert len(fd) == 2
    assert "a" in fd
    assert list(fd) == ["a", "b"]
    assert hash(fd) == hash(FrozenDict({"a": 1, "b": 2}))

    # Immutability
    with pytest.raises(TypeError):
        fd["a"] = 10  # type: ignore[index]
    with pytest.raises(TypeError):
        del fd["a"]  # type: ignore[attr-defined]

    assert repr(fd) == "FrozenDict({'a': 1, 'b': 2})"
    assert fd == {"a": 1, "b": 2}


def test_chunked():
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(chunked([], 3)) == []
    assert list(chunked([1, 2], 5)) == [[1, 2]]

    with pytest.raises(ValueError, match="size must be a positive integer"):
        list(chunked([1, 2], 0))
    with pytest.raises(ValueError, match="size must be a positive integer"):
        list(chunked([1, 2], -1))
    with pytest.raises(TypeError, match="size must be an integer"):
        list(chunked([1, 2], True))  # type: ignore[arg-type]


def test_flatten():
    assert list(flatten([[1, 2], [3, [4, 5]]], depth=1)) == [1, 2, 3, [4, 5]]
    assert list(flatten([[1, 2], [3, [4, 5]]], depth=2)) == [1, 2, 3, 4, 5]
    # Strings are not split into characters
    assert list(flatten(["hello", ["world"]])) == ["hello", "world"]


def test_collections_bare_string_guards():
    with pytest.raises(TypeError, match="items must not be a string or bytes"):
        unique("hello")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="items must not be a string or bytes"):
        unique(b"hello")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="items must not be a string or bytes"):
        group_by("hello", key=lambda x: x)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="items must not be a string or bytes"):
        index_by("hello", key=lambda x: x)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="items must not be a string or bytes"):
        partition("hello", predicate=lambda x: True)  # type: ignore[arg-type]


# =============================================================================
# #22–#26: structures.RingBuffer, PriorityQueue, BiMap & Parity
# =============================================================================

def test_generic_ring_buffer_is_full_and_empty_and_peek():
    buf = GenericRingBuffer[int](capacity=3)
    assert buf.is_empty
    assert not buf.is_full
    assert len(buf) == 0

    buf.append(10)
    assert not buf.is_empty
    assert not buf.is_full
    assert buf.peek() == 10

    buf.append(20)
    buf.append(30)
    assert buf.is_full
    assert len(buf) == 3

    # popleft
    popped = buf.popleft()
    assert popped == 10
    assert not buf.is_full
    assert len(buf) == 2
    assert buf.peek() == 20

    # Eviction on overflow
    buf.append(40)
    buf.append(50)  # capacity=3, data: [30, 40, 50]
    assert buf.peek() == 30
    assert buf.peek_newest() == 50


def test_priority_queue():
    pq = PriorityQueue[str](maxsize=3)
    assert pq.is_empty
    assert not pq.is_full
    assert pq.maxsize == 3

    pq.push("low-priority", priority=10)
    pq.push("high-priority", priority=1)
    pq.push("medium-priority", priority=5)

    assert pq.is_full
    assert len(pq) == 3
    assert pq.peek() == "high-priority"

    with pytest.raises(OverflowError, match="PriorityQueue is full"):
        pq.push("extra", priority=0)

    assert pq.pop() == "high-priority"
    assert pq.pop() == "medium-priority"
    assert pq.pop() == "low-priority"
    assert pq.is_empty

    with pytest.raises(IndexError, match="empty PriorityQueue"):
        pq.pop()
    with pytest.raises(IndexError, match="empty PriorityQueue"):
        pq.peek()


def test_bimap():
    bm = BiMap[str, int]({"one": 1, "two": 2})
    assert len(bm) == 2
    assert bm["one"] == 1
    assert bm["two"] == 2

    # Inverse lookup
    inv = bm.inverse
    assert inv[1] == "one"
    assert inv[2] == "two"
    assert inv.inverse is bm

    # Mutating via forward reflects in inverse
    bm["three"] = 3
    assert inv[3] == "three"

    # Mutating via inverse reflects in forward
    inv[4] = "four"
    assert bm["four"] == 4

    # Deleting reflects
    del bm["one"]
    assert 1 not in inv
    assert "one" not in bm

    # Value collision error
    with pytest.raises(ValueError, match="already mapped"):
        bm["duplicate_three"] = 3
