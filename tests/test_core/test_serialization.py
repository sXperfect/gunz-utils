from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path
from types import MappingProxyType

from gunz_utils.serialization import canonical_json, json_loads, to_jsonable


@dataclasses.dataclass
class Example:
    name: str
    path: Path


class TestSerialization(unittest.TestCase):
    def test_canonical_order(self) -> None:
        self.assertEqual(canonical_json({"b": 2, "a": 1}), '{"a":1,"b":2}')

    def test_dataclass_and_path(self) -> None:
        value = to_jsonable(Example("x", Path("/tmp/x")))
        self.assertEqual(value, {"name": "x", "path": "/tmp/x"})

    def test_round_trip(self) -> None:
        encoded = canonical_json({"hello": [1, 2]})
        self.assertEqual(json_loads(encoded), {"hello": [1, 2]})

    def test_bytes_are_explicitly_rejected(self) -> None:
        with self.assertRaises(TypeError):
            canonical_json({"raw": b"x"})

    def test_recursive_structure_depth_is_bounded(self) -> None:
        value: object = "leaf"
        for _ in range(6):
            value = [value]

        with self.assertRaisesRegex(ValueError, "maximum nesting depth"):
            to_jsonable(
                value,
                _max_depth=3,
            )

    def test_mapping_key_normalization_collision_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "mapping keys collide",
        ):
            canonical_json({1: "integer", "1": "string"})



@dataclasses.dataclass(frozen=True)
class FrozenMappingExample:
    values: object


class TestImmutableDataclassSerialization(unittest.TestCase):
    def test_mapping_proxy_inside_dataclass_is_supported(self) -> None:
        value = FrozenMappingExample(
            MappingProxyType(
                {
                    "nested": MappingProxyType(
                        {"value": 1}
                    )
                }
            )
        )

        self.assertEqual(
            to_jsonable(value),
            {
                "values": {
                    "nested": {
                        "value": 1,
                    }
                }
            },
        )
