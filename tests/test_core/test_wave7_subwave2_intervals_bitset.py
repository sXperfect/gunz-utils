"""Tests for Wave 7 Sub-Wave 2: Range Queries, Interval Trees & Bitsets."""

from gunz_utils.bitset import BitSet
from gunz_utils.intervals import Interval, IntervalTree


def test_interval_overlaps_and_tree():
    iv1 = Interval(10.0, 20.0, data="A")
    iv2 = Interval(15.0, 25.0, data="B")
    iv3 = Interval(30.0, 40.0, data="C")

    assert iv1.overlaps(iv2)
    assert not iv1.overlaps(iv3)
    assert iv1.contains_point(15.0)
    assert not iv1.contains_point(20.0)

    tree = IntervalTree()
    tree.insert(iv1)
    tree.insert(iv2)
    tree.insert(iv3)

    assert len(tree) == 3

    # Overlaps with [18, 22)
    overlaps = tree.find_overlapping((18.0, 22.0))
    datas = [x.data for x in overlaps]
    assert datas == ["A", "B"]

    # Point query at 35.0
    containing = tree.find_containing(35.0)
    assert len(containing) == 1
    assert containing[0].data == "C"


def test_bitset_operations():
    bs = BitSet(100)
    assert len(bs) == 100
    assert bs.popcount() == 0

    bs.set(5, True)
    bs.set(10, True)
    bs.set(65, True)  # in 2nd 64-bit limb

    assert bs.get(5)
    assert bs.get(10)
    assert bs.get(65)
    assert not bs.get(6)
    assert bs.popcount() == 3

    bs.flip(5)
    assert not bs.get(5)
    assert bs.popcount() == 2


def test_bitset_algebra_and_serialization():
    b1 = BitSet(10)
    b2 = BitSet(10)
    b1.set(1)
    b1.set(2)
    b2.set(2)
    b2.set(3)

    band = b1 & b2
    assert band.popcount() == 1
    assert band.get(2)

    bor = b1 | b2
    assert bor.popcount() == 3

    bxor = b1 ^ b2
    assert bxor.popcount() == 2

    # Serialization roundtrip
    raw = b1.to_bytes()
    restored = BitSet.from_bytes(raw, size=10)
    assert restored.popcount() == 2
    assert restored.get(1)
    assert restored.get(2)
