"""Tests for Next-Wave Wave 1 items (#1 - #14): Core structures, containers, diffing."""

from __future__ import annotations

import math
import unittest
from gunz_utils import deep_pop, windowed
from gunz_utils.buffers import as_readonly_view, dispatch
from gunz_utils.collections import group_by, index_by, partition, unique
from gunz_utils.dict_utils import deep_merge
from gunz_utils.structures import (
    DeepDifference,
    RingBuffer,
    bottom_k,
    deep_diff,
    freeze_structure,
    retain_priority_and_recent,
    stable_unique,
    top_k,
)


class TestWave1Structures(unittest.TestCase):
    def test_memoryview_in_deep_diff(self) -> None:
        # Item 1: memoryview treated as scalar leaf
        m1 = memoryview(b"hello")
        m2 = memoryview(b"hello")
        m3 = memoryview(b"world")
        self.assertEqual(deep_diff(m1, m2), [])
        diffs = deep_diff(m1, m3)
        self.assertEqual(len(diffs), 1)
        self.assertEqual(diffs[0].kind, "value")

    def test_bool_marker_collision(self) -> None:
        # Item 2: boolean deduplication marker does not collide with (bool, True)
        from gunz_utils.structures import _BOOL_SENTINEL

        items = [True, (bool, True), False, (bool, False)]
        self.assertEqual(list(stable_unique(items)), items)
        self.assertEqual(unique(items), items)

        merged = deep_merge(
            {"list": [True, (bool, True)]},
            {"list": [True, False]},
            list_strategy="dedup",
        )
        self.assertEqual(merged["list"], [True, (bool, True), False])

    def test_ring_buffer_methods(self) -> None:
        # Item 3: RingBuffer ergonomics
        buf = RingBuffer(3)
        self.assertEqual(buf.capacity, 3)
        self.assertFalse(bool(buf))
        self.assertEqual(len(buf), 0)
        self.assertEqual(buf.to_list(), [])

        with self.assertRaises(IndexError):
            buf.peek_oldest()
        with self.assertRaises(IndexError):
            buf.peek_newest()

        buf.extend([1, 2])
        self.assertTrue(bool(buf))
        self.assertEqual(len(buf), 2)
        self.assertEqual(buf.peek_oldest(), 1)
        self.assertEqual(buf.peek_newest(), 2)
        self.assertEqual(buf[0], 1)
        self.assertEqual(buf[1], 2)

        buf.append(3)
        self.assertEqual(buf.to_list(), [1, 2, 3])
        buf.append(4)  # evicts 1
        self.assertEqual(buf.to_list(), [2, 3, 4])
        self.assertEqual(buf.peek_oldest(), 2)
        self.assertEqual(buf.peek_newest(), 4)

        buf2 = RingBuffer(3)
        buf2.extend([2, 3, 4])
        self.assertEqual(buf, buf2)
        self.assertIn("RingBuffer([2, 3, 4], capacity=3)", repr(buf))

        buf.clear()
        self.assertEqual(len(buf), 0)
        self.assertFalse(bool(buf))

    def test_top_k_and_bottom_k(self) -> None:
        # Items 4 & 5: top_k and bottom_k with key support
        records = [{"id": "a", "val": 30}, {"id": "b", "val": 10}, {"id": "c", "val": 20}]
        top = top_k(records, 2, key=lambda r: r["val"])
        self.assertEqual([r["id"] for r in top], ["a", "c"])

        bottom = bottom_k(records, 2, key=lambda r: r["val"])
        self.assertEqual([r["id"] for r in bottom], ["b", "c"])

        with self.assertRaises(TypeError):
            top_k([1, 2], 1, key="not callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            bottom_k([1, 2], 1, key="not callable")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            bottom_k([1, 2], -1)

    def test_retain_priority_and_recent(self) -> None:
        # Item 6: retain_priority_and_recent validation and k=0
        with self.assertRaises(TypeError):
            retain_priority_and_recent([1, 2], is_priority="bad", max_recent=1)  # type: ignore[arg-type]

        data = [1, 2, 3, 4, 5]
        # max_recent=0 retains only priority items
        res = retain_priority_and_recent(data, is_priority=lambda x: x % 2 == 1, max_recent=0)
        self.assertEqual(res, [1, 3, 5])

    def test_deep_diff_nan_equal_and_max_depth(self) -> None:
        # Item 7: deep_diff nan_equal and max_depth
        n1 = {"val": float("nan")}
        n2 = {"val": float("nan")}
        self.assertEqual(len(deep_diff(n1, n2, nan_equal=False)), 1)
        self.assertEqual(deep_diff(n1, n2, nan_equal=True), [])

        tree1 = {"a": {"b": {"c": 1}}}
        tree2 = {"a": {"b": {"c": 2}}}
        diffs_deep = deep_diff(tree1, tree2, max_depth=1)
        self.assertEqual(len(diffs_deep), 1)
        self.assertEqual(diffs_deep[0].path, "a")

        with self.assertRaises(ValueError):
            deep_diff(tree1, tree2, max_depth=-1)

    def test_freeze_structure_unhashable_element_in_set(self) -> None:
        # Item 8: descriptive TypeError when set element freezes to unhashable
        from collections.abc import Set

        class FakeSet(Set):
            def __contains__(self, x: object) -> bool:
                return False

            def __len__(self) -> int:
                return 1

            def __iter__(self):
                return iter([{"key": "val"}])

        with self.assertRaises(TypeError) as ctx:
            freeze_structure(FakeSet())
        self.assertIn("frozen set elements must be hashable", str(ctx.exception))
        self.assertIsNotNone(freeze_structure({"a": 1}))

    def test_dispatch_validation(self) -> None:
        # Item 9: dispatch callable validation
        with self.assertRaises(TypeError):
            dispatch("not callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            dispatch(lambda: 1, "not callable")  # type: ignore[arg-type]

        def ref():
            return "ref"

        def acc():
            return "acc"

        self.assertEqual(dispatch(ref, None)(), "ref")
        self.assertEqual(dispatch(ref, acc)(), "acc")

    def test_as_readonly_view(self) -> None:
        # Item 10: as_readonly_view
        v1 = as_readonly_view(b"abc")
        self.assertEqual(bytes(v1), b"abc")
        self.assertTrue(v1.readonly)

        v2 = as_readonly_view(bytearray(b"xyz"))
        self.assertEqual(bytes(v2), b"xyz")

        with self.assertRaises(TypeError):
            as_readonly_view([1, 2, 3])  # type: ignore[arg-type]

    def test_collections_eager_validation_and_index_by_strict(self) -> None:
        # Items 11 & 12
        with self.assertRaises(TypeError):
            unique([], key="not callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            group_by([], "not callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            index_by([], "not callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            partition([], "not callable")  # type: ignore[arg-type]

        items = [{"id": 1, "name": "first"}, {"id": 1, "name": "second"}]
        # Default strict=False overwrites
        self.assertEqual(index_by(items, lambda x: x["id"]) [1]["name"], "second")
        # strict=True raises ValueError on duplicate key
        with self.assertRaises(ValueError) as ctx:
            index_by(items, lambda x: x["id"], strict=True)
        self.assertIn("duplicate key in index_by", str(ctx.exception))

    def test_deep_pop(self) -> None:
        # Item 13: deep_pop
        target = {"a": {"b": {"c": 42, "d": 99}}}
        val = deep_pop(target, "a.b.c")
        self.assertEqual(val, 42)
        self.assertNotIn("c", target["a"]["b"])
        self.assertEqual(target["a"]["b"]["d"], 99)

        # with default
        self.assertEqual(deep_pop(target, "a.b.missing", default="fallback"), "fallback")
        self.assertEqual(deep_pop(target, "a.missing.c", default="fallback"), "fallback")

        # without default raises KeyError
        with self.assertRaises(KeyError):
            deep_pop(target, "a.b.missing")
        with self.assertRaises(KeyError):
            deep_pop(target, "a.missing.c")

        with self.assertRaises(TypeError):
            deep_pop([1, 2, 3], "a.b")  # type: ignore[arg-type]

    def test_windowed(self) -> None:
        # Item 14: windowed
        self.assertEqual(list(windowed([1, 2, 3, 4, 5], 3)), [(1, 2, 3), (2, 3, 4), (3, 4, 5)])
        self.assertEqual(list(windowed([1, 2, 3, 4, 5], 3, step=2)), [(1, 2, 3), (3, 4, 5)])
        self.assertEqual(list(windowed([1, 2], 3)), [])
        self.assertEqual(list(windowed([], 3)), [])

        with self.assertRaises(ValueError):
            list(windowed([1, 2], 0))
        with self.assertRaises(ValueError):
            list(windowed([1, 2], 2, step=0))


if __name__ == "__main__":
    unittest.main()
