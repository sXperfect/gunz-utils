"""Tests for lazy iteration helpers."""

from __future__ import annotations

import unittest

from gunz_utils.iteration import batched, chunked, first, flatten


class TestChunked(unittest.TestCase):
    def test_exact_fit(self) -> None:
        self.assertEqual(
            list(chunked([1, 2, 3, 4], 2)),
            [(1, 2), (3, 4)],
        )

    def test_partial_final_group(self) -> None:
        self.assertEqual(
            list(chunked([1, 2, 3, 4, 5], 2)),
            [(1, 2), (3, 4), (5,)],
        )

    def test_empty_iterable(self) -> None:
        self.assertEqual(list(chunked([], 3)), [])

    def test_n_equal_to_length(self) -> None:
        self.assertEqual(list(chunked([1, 2, 3], 3)), [(1, 2, 3)])

    def test_n_equals_one(self) -> None:
        self.assertEqual(
            list(chunked([1, 2, 3], 1)),
            [(1,), (2,), (3,)],
        )

    def test_n_greater_than_length(self) -> None:
        self.assertEqual(list(chunked([1, 2], 10)), [(1, 2)])

    def test_n_zero_raises(self) -> None:
        with self.assertRaises(ValueError):
            list(chunked([1, 2, 3], 0))

    def test_n_negative_raises(self) -> None:
        with self.assertRaises(ValueError):
            list(chunked([1, 2, 3], -1))

    def test_accepts_generator(self) -> None:
        #? One-pass generator: chunked must consume lazily without buffering.
        def gen():
            yield from range(5)

        self.assertEqual(list(chunked(gen(), 2)), [(0, 1), (2, 3), (4,)])

    def test_returns_tuples_not_lists(self) -> None:
        groups = list(chunked([1, 2, 3], 2))
        for group in groups:
            self.assertIsInstance(group, tuple)

    def test_yielded_tuples_are_hashable(self) -> None:
        #? Tuples must be hashable so callers can use them as dict keys / set elements.
        groups = list(chunked([1, 2, 3, 4], 2))
        self.assertEqual(len(set(groups)), 2)

    def test_yielded_groups_are_independent(self) -> None:
        #? Consuming one group's inner iteration must not affect subsequent groups.
        it = chunked([1, 2, 3, 4, 5, 6], 2)
        first_group = next(it)
        for x in first_group:
            if x == 1:
                break
        self.assertEqual(next(it), (3, 4))
        self.assertEqual(next(it), (5, 6))


class TestBatched(unittest.TestCase):
    def test_exact_fit(self) -> None:
        self.assertEqual(
            list(batched([1, 2, 3, 4], 2)),
            [[1, 2], [3, 4]],
        )

    def test_partial_final_group(self) -> None:
        self.assertEqual(
            list(batched([1, 2, 3, 4, 5], 2)),
            [[1, 2], [3, 4], [5]],
        )

    def test_empty_iterable(self) -> None:
        self.assertEqual(list(batched([], 3)), [])

    def test_n_equals_one(self) -> None:
        self.assertEqual(
            list(batched([1, 2, 3], 1)),
            [[1], [2], [3]],
        )

    def test_n_greater_than_length(self) -> None:
        self.assertEqual(list(batched([1, 2], 10)), [[1, 2]])

    def test_n_zero_raises(self) -> None:
        with self.assertRaises(ValueError):
            list(batched([1, 2, 3], 0))

    def test_n_negative_raises(self) -> None:
        with self.assertRaises(ValueError):
            list(batched([1, 2, 3], -2))

    def test_returns_lists_not_tuples(self) -> None:
        groups = list(batched([1, 2, 3], 2))
        for group in groups:
            self.assertIsInstance(group, list)

    def test_yielded_list_is_mutable(self) -> None:
        #? Mutable-list contract: append must work on the yielded container.
        groups = batched([1, 2, 3, 4], 2)
        first_group = next(groups)
        first_group.append("x")
        self.assertEqual(first_group, [1, 2, "x"])

    def test_yielded_lists_are_independent(self) -> None:
        #? Each yielded list must be a fresh object so appending to one
        #? does not leak into siblings.
        groups = list(batched([1, 2, 3, 4], 2))
        groups[0].append("x")
        self.assertEqual(groups[1], [3, 4])


class TestFlatten(unittest.TestCase):
    def test_fully_recursive_default(self) -> None:
        self.assertEqual(
            list(flatten([[1, 2], [3, [4, 5]]])),
            [1, 2, 3, 4, 5],
        )

    def test_max_depth_one(self) -> None:
        #? Lodash semantics: one level of flattening — the outermost
        #? container is unwrapped, but nested containers are preserved.
        self.assertEqual(
            list(flatten([[1, [2, [3]]]], max_depth=1)),
            [1, [2, [3]]],
        )

    def test_max_depth_two(self) -> None:
        #? Two levels of flattening — outer + inner list unwrapped, the
        #? deepest list preserved as a leaf.
        self.assertEqual(
            list(flatten([[1, [2, [3]]]], max_depth=2)),
            [1, 2, [3]],
        )

    def test_max_depth_three(self) -> None:
        #? Three levels of flattening — fully unwrapped for this input.
        self.assertEqual(
            list(flatten([[1, [2, [3]]]], max_depth=3)),
            [1, 2, 3],
        )

    def test_max_depth_zero_passes_through(self) -> None:
        #? At depth 0 the inner walker yields the input verbatim — useful
        #? for normalizing a single non-container item.
        self.assertEqual(list(flatten(42, max_depth=0)), [42])

    def test_max_depth_negative_raises(self) -> None:
        with self.assertRaises(ValueError):
            list(flatten([1, 2], max_depth=-1))

    def test_custom_types_set(self) -> None:
        #? With `types=(list, set)`, sets are descended into but tuples are not.
        result = list(flatten([[{1, 2}], [(3,)]], types=(list, set)))
        self.assertEqual(set(result), {1, 2, (3,)})

    def test_dict_not_descended_by_default(self) -> None:
        #? Dicts are not in the default `types`, so the dict itself is yielded.
        d = {"a": 1, "b": 2}
        self.assertEqual(list(flatten([d])), [d])

    def test_string_not_descended_by_default(self) -> None:
        #? `str` is not in the default `types=(list, tuple)`, so each string
        #? is yielded as a single leaf rather than exploded into characters.
        self.assertEqual(list(flatten(["ab", "cd"])), ["ab", "cd"])

    def test_mixed_nested_types(self) -> None:
        #? Tuple is descended, list is descended, dict is a leaf, str is a leaf.
        nested = ([1, (2, 3)], {"k": "v"}, "hello")
        result = list(flatten(nested))
        self.assertEqual(result, [1, 2, 3, {"k": "v"}, "hello"])

    def test_generator_input(self) -> None:
        def gen():
            yield [1, 2]
            yield (3, [4, 5])

        self.assertEqual(list(flatten(gen())), [1, 2, 3, 4, 5])

    def test_single_element(self) -> None:
        self.assertEqual(list(flatten(42)), [42])

    def test_empty_iterable(self) -> None:
        self.assertEqual(list(flatten([])), [])


class TestFirst(unittest.TestCase):
    def test_non_empty_list(self) -> None:
        self.assertEqual(first([1, 2, 3]), 1)

    def test_empty_list_default_none(self) -> None:
        self.assertIsNone(first([]))

    def test_empty_list_explicit_default(self) -> None:
        self.assertEqual(first([], default="missing"), "missing")

    def test_generator_input(self) -> None:
        #? Iterators are consumed only until the first element.
        self.assertEqual(first(iter([42, 99])), 42)

    def test_returns_none_for_empty_when_default_is_none(self) -> None:
        #? When iterable is empty, default (None) is returned.
        self.assertIsNone(first(iter([]), default=None))

    def test_returns_first_even_if_none(self) -> None:
        #? `None` is a valid item — it must be returned, not treated as missing.
        self.assertIsNone(first([None, 1, 2]))

    def test_iterates_only_once(self) -> None:
        #? `first` must not exhaust the underlying iterator.
        it = iter([1, 2, 3])
        self.assertEqual(first(it), 1)
        self.assertEqual(next(it), 2)
        self.assertEqual(next(it), 3)


class TestIntegration(unittest.TestCase):
    def test_chunked_then_flatten(self) -> None:
        #? `flatten` descends into the tuples yielded by `chunked` (default
        #? `types=(list, tuple)`), so the result is a single flat sequence —
        #? the chunk boundary structure is dissolved.
        result = list(flatten(chunked(range(6), 2)))
        self.assertEqual(result, [0, 1, 2, 3, 4, 5])

    def test_batched_then_flatten(self) -> None:
        #? Same as `chunked` above: `flatten` descends into the lists from
        #? `batched` and unwraps them into a single flat sequence.
        result = list(flatten(batched(range(6), 2)))
        self.assertEqual(result, [0, 1, 2, 3, 4, 5])

    def test_first_of_chunked(self) -> None:
        #? `first` works on the generator returned by `chunked`.
        self.assertEqual(first(chunked([10, 20, 30, 40], 2)), (10, 20))


if __name__ == "__main__":
    unittest.main()
