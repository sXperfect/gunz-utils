"""Tests for nested-dict utilities."""

from __future__ import annotations

import unittest

from gunz_utils.dict_utils import deep_get, deep_merge, deep_set


class TestDeepGet(unittest.TestCase):
    def test_flat_dict(self) -> None:
        self.assertEqual(deep_get({"a": 1}, "a"), 1)

    def test_nested_dict(self) -> None:
        self.assertEqual(deep_get({"a": {"b": 1}}, "a.b"), 1)

    def test_deeply_nested_dict(self) -> None:
        source = {"a": {"b": {"c": {"d": 5}}}}
        self.assertEqual(deep_get(source, "a.b.c.d"), 5)

    def test_sequence_path_form(self) -> None:
        self.assertEqual(deep_get({"a": {"b": 1}}, ["a", "b"]), 1)

    def test_custom_separator(self) -> None:
        self.assertEqual(deep_get({"a": {"b": 1}}, "a/b", separator="/"), 1)

    def test_missing_key_returns_default(self) -> None:
        self.assertEqual(deep_get({"a": 1}, "b", default=42), 42)

    def test_missing_key_default_none(self) -> None:
        self.assertIsNone(deep_get({"a": 1}, "b", default=None))

    def test_missing_key_no_default_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            deep_get({"a": 1}, "b")

    def test_traversal_through_scalar_returns_default(self) -> None:
        #? Walking past a scalar must NOT raise TypeError; callers probe
        #? config trees where intermediate nodes may be any JSON value.
        self.assertEqual(deep_get({"a": 1}, "a.b", default=42), 42)

    def test_traversal_through_scalar_no_default_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            deep_get({"a": 1}, "a.b")

    def test_traversal_through_list_returns_default(self) -> None:
        #? Lists are not Mappings; keying into one falls through to the
        #? not-found branch rather than raising TypeError.
        self.assertEqual(deep_get({"a": [1, 2]}, "a.b", default=42), 42)

    def test_empty_string_path_raises_valueerror(self) -> None:
        with self.assertRaises(ValueError):
            deep_get({}, "")

    def test_path_with_empty_segment_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_get({}, "a..b")

    def test_path_with_leading_separator_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_get({}, ".a")

    def test_path_with_trailing_separator_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_get({}, "a.")

    def test_empty_sequence_path_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_get({}, [])

    def test_custom_separator_with_sequence_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_get({}, ["a"], separator="/")


class TestDeepSet(unittest.TestCase):
    def setUp(self) -> None:
        #? Each test starts from a fresh empty dict; deep_set mutates in place.
        self.target: dict = {}

    def test_set_in_empty_dict_creates_intermediates(self) -> None:
        deep_set(self.target, "a.b.c", 42)
        self.assertEqual(self.target, {"a": {"b": {"c": 42}}})

    def test_set_in_existing_dict(self) -> None:
        deep_set(self.target, "a.b", 1)
        deep_set(self.target, "a.c", 2)
        self.assertEqual(self.target, {"a": {"b": 1, "c": 2}})

    def test_set_overrides_existing_leaf(self) -> None:
        deep_set(self.target, "a.b", 1)
        deep_set(self.target, "a.b", 99)
        self.assertEqual(self.target, {"a": {"b": 99}})

    def test_sequence_path_form(self) -> None:
        deep_set(self.target, ["a", "b"], 1)
        self.assertEqual(self.target, {"a": {"b": 1}})

    def test_custom_separator(self) -> None:
        deep_set(self.target, "a/b", 1, separator="/")
        self.assertEqual(self.target, {"a": {"b": 1}})

    def test_intermediate_non_dict_replaced(self) -> None:
        #? Lodash-style _.set behavior: a non-dict intermediate is replaced
        #? with a fresh dict. The previous value (5) is silently lost.
        deep_set({"a": 5}, "a.b", 1)  # does not mutate self.target
        target = {"a": 5}
        deep_set(target, "a.b", 1)
        self.assertEqual(target, {"a": {"b": 1}})

    def test_returns_none(self) -> None:
        #? Explicit None return makes the "mutates in place; no return value"
        #? contract clear for callers that might accidentally bind the result.
        result = deep_set(self.target, "a", 1)
        self.assertIsNone(result)

    def test_empty_path_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_set(self.target, "", 1)

    def test_path_with_empty_segment_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_set(self.target, "a..b", 1)


class TestDeepMerge(unittest.TestCase):
    def test_shallow_merge_disjoint_keys(self) -> None:
        self.assertEqual(deep_merge({"a": 1}, {"b": 2}), {"a": 1, "b": 2})

    def test_shallow_merge_override_wins_on_scalar_conflict(self) -> None:
        self.assertEqual(deep_merge({"a": 1}, {"a": 2}), {"a": 2})

    def test_recursive_dict_merge(self) -> None:
        result = deep_merge({"a": {"b": 1}}, {"a": {"c": 2}})
        self.assertEqual(result["a"], {"b": 1, "c": 2})

    def test_returns_new_dict_does_not_mutate_base(self) -> None:
        base = {"a": {"b": 1}}
        deep_merge(base, {"a": {"c": 2}})
        self.assertEqual(base, {"a": {"b": 1}})

    def test_returns_new_dict_does_not_mutate_override(self) -> None:
        override = {"a": {"c": 2}}
        deep_merge({"a": {"b": 1}}, override)
        self.assertEqual(override, {"a": {"c": 2}})

    def test_list_strategy_replace_default(self) -> None:
        #? Default strategy: override list fully replaces the base list.
        self.assertEqual(deep_merge({"xs": [1, 2]}, {"xs": [3]}), {"xs": [3]})

    def test_list_strategy_concat(self) -> None:
        self.assertEqual(
            deep_merge({"xs": [1, 2]}, {"xs": [3]}, list_strategy="concat"),
            {"xs": [1, 2, 3]},
        )

    def test_list_strategy_dedup_preserves_order(self) -> None:
        #? First occurrence wins; order is base then override.
        self.assertEqual(
            deep_merge({"xs": [1, 2, 3]}, {"xs": [2, 4]}, list_strategy="dedup"),
            {"xs": [1, 2, 3, 4]},
        )

    def test_list_strategy_dedup_handles_unhashable_items(self) -> None:
        #? Dicts are unhashable: the dedup path falls through and appends
        #? every item. The contract is "no crash", not "actual deduplication".
        result = deep_merge(
            {"xs": [{"x": 1}]},
            {"xs": [{"x": 1}, {"y": 2}]},
            list_strategy="dedup",
        )
        self.assertEqual(result["xs"], [{"x": 1}, {"y": 2}])

    def test_dedup_does_not_confuse_hash_collisions(self) -> None:
        self.assertEqual(
            deep_merge({"xs": [-1]}, {"xs": [-2]}, list_strategy="dedup"),
            {"xs": [-1, -2]},
        )

    def test_non_dict_override_on_dict_base_replaces(self) -> None:
        #? Mixed-type pair: override wins without recursing into the dict.
        self.assertEqual(deep_merge({"a": {"x": 1}}, {"a": 5}), {"a": 5})

    def test_invalid_list_strategy_raises(self) -> None:
        with self.assertRaises(ValueError):
            deep_merge({"a": 1}, {"a": 1}, list_strategy="bogus")  # type: ignore[arg-type]

    def test_empty_both_inputs_returns_empty(self) -> None:
        self.assertEqual(deep_merge({}, {}), {})

    def test_merge_isolates_nested_subtrees_from_caller_mutation(self) -> None:
        base = {"a": {"nested": 1, "items": [10, 20]}, "base_only": {"secret": "x"}}
        override = {
            "b": {"other": 2, "tags": ["a", "b"]},
            "override_only": {"flag": True},
        }
        merged = deep_merge(base, override)

        # Mutate merged dict subtrees
        merged["base_only"]["secret"] = "mutated"
        merged["override_only"]["flag"] = False
        merged["a"]["items"].append(30)
        merged["b"]["tags"].append("c")

        # Caller input structures must remain untouched
        self.assertEqual(base["base_only"]["secret"], "x")
        self.assertEqual(override["override_only"]["flag"], True)
        self.assertEqual(base["a"]["items"], [10, 20])
        self.assertEqual(override["b"]["tags"], ["a", "b"])


class TestIntegration(unittest.TestCase):
    """Cross-function integration tests."""

    def test_set_then_get(self) -> None:
        #? deep_set writes a value that deep_get can immediately read back.
        target: dict = {}
        deep_set(target, "server.host", "localhost")
        deep_set(target, "server.port", 8080)
        self.assertEqual(deep_get(target, "server.host"), "localhost")
        self.assertEqual(deep_get(target, "server.port"), 8080)

    def test_merge_then_get(self) -> None:
        #? A merged config tree should be navigable by deep_get.
        cfg = deep_merge(
            {"api": {"timeout": 30, "retries": 3}},
            {"api": {"retries": 5}},
        )
        self.assertEqual(deep_get(cfg, "api.timeout"), 30)
        self.assertEqual(deep_get(cfg, "api.retries"), 5)

    def test_set_then_merge(self) -> None:
        #? After deep_set places a value, deep_merge should still see and
        #? combine it without crashing on the structure.
        target: dict = {}
        deep_set(target, "a.b", 1)
        result = deep_merge(target, {"a": {"c": 2}})
        self.assertEqual(result["a"], {"b": 1, "c": 2})

    def test_complex_config_merge_with_lists(self) -> None:
        #? Realistic config tree exercising dict + list + nested merge.
        base = {
            "logging": {
                "level": "INFO",
                "handlers": [
                    {"type": "console", "format": "plain"},
                ],
            },
            "version": 1,
        }
        override = {
            "logging": {
                "level": "DEBUG",
                "handlers": [
                    {"type": "file", "path": "/var/log/app.log"},
                ],
            },
        }
        result = deep_merge(base, override, list_strategy="concat")
        self.assertEqual(result["logging"]["level"], "DEBUG")
        self.assertEqual(len(result["logging"]["handlers"]), 2)
        self.assertEqual(result["logging"]["handlers"][0]["type"], "console")
        self.assertEqual(result["logging"]["handlers"][1]["type"], "file")
        self.assertEqual(result["version"], 1)


if __name__ == "__main__":
    unittest.main()
