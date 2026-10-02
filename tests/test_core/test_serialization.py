from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path
from types import MappingProxyType

import gunz_utils.serialization as ser_mod
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

    def test_non_finite_floats_are_rejected(self) -> None:
        for val in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaisesRegex(
                ValueError,
                "Out of range float values are not JSON compliant",
            ):
                to_jsonable(val)
            with self.assertRaisesRegex(
                ValueError,
                "Out of range float values are not JSON compliant",
            ):
                to_jsonable({"nested": val})
            with self.assertRaisesRegex(
                ValueError,
                "Out of range float values are not JSON compliant",
            ):
                to_jsonable([1.0, val])



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


class TestSerializationDifferential(unittest.TestCase):
    """Differential tests comparing native C acceleration and pure-Python fallback."""

    def test_native_vs_python_equivalence_on_clean_and_complex_inputs(self) -> None:
        test_cases = [
            {"a": 1, "b": [2, 3, "four", True, None]},
            {"nested": {"x": 1.5, "y": -99.25}},
            [1, 2, [3, [4, 5]]],
            {"items": [{"k": "v"}, {"k2": "v2"}]},
            Example("test_name", Path("/var/log")),
            {1: "int_key", 2: "int_key_2"},
            {"tags": ["b", "a"]},
        ]

        for case in test_cases:
            # Native run (dispatched)
            native_jsonable = to_jsonable(case)
            native_json = canonical_json(case)

            # Pure Python run (with _accel_is_json_clean mocked to None)
            saved_clean = ser_mod._accel_is_json_clean
            try:
                ser_mod._accel_is_json_clean = None
                py_jsonable = to_jsonable(case)
                py_json = canonical_json(case)
            finally:
                ser_mod._accel_is_json_clean = saved_clean

            # Serialized representations must be identical
            self.assertEqual(native_json, py_json)
            # Converted values must be equal in content
            self.assertEqual(native_jsonable, py_jsonable)

    def test_native_vs_python_exception_parity(self) -> None:
        err_float = "Out of range float values are not JSON compliant"
        err_bytes = "bytes are not implicitly JSON serializable"
        error_cases = [
            (float("nan"), ValueError, err_float),
            (float("inf"), ValueError, err_float),
            (float("-inf"), ValueError, err_float),
            (b"raw bytes", TypeError, err_bytes),
            ({"nested": b"bytes"}, TypeError, err_bytes),
            ([b"bytes"], TypeError, err_bytes),
        ]

        for val, exc_type, match_str in error_cases:
            with self.subTest(val=val):
                # Native run
                with self.assertRaisesRegex(exc_type, match_str):
                    to_jsonable(val)

                # Pure Python run
                saved_clean = ser_mod._accel_is_json_clean
                try:
                    ser_mod._accel_is_json_clean = None
                    with self.assertRaisesRegex(exc_type, match_str):
                        to_jsonable(val)
                finally:
                    ser_mod._accel_is_json_clean = saved_clean

    def test_cycle_and_recursion_limit_parity(self) -> None:
        """Verify cycle detection depth limit parity between native and python."""
        cycle_list: list[object] = []
        cycle_list.append(cycle_list)

        cycle_dict: dict[str, object] = {}
        cycle_dict["self"] = cycle_dict

        for cycle_obj in (cycle_list, cycle_dict):
            # Native run
            with self.assertRaisesRegex(ValueError, "maximum nesting depth"):
                to_jsonable(cycle_obj)

            # Pure Python run
            saved_clean = ser_mod._accel_is_json_clean
            try:
                ser_mod._accel_is_json_clean = None
                with self.assertRaisesRegex(ValueError, "maximum nesting depth"):
                    to_jsonable(cycle_obj)
            finally:
                ser_mod._accel_is_json_clean = saved_clean

    def test_clean_input_identity_contract(self) -> None:
        """Document and verify object identity semantics for clean containers."""
        clean_dict = {"a": 1, "b": [1, 2]}
        clean_list = [1, 2, "three"]

        if ser_mod._accel_is_json_clean is not None:
            # Native acceleration avoids re-allocating clean input trees
            self.assertIs(to_jsonable(clean_dict), clean_dict)
            self.assertIs(to_jsonable(clean_list), clean_list)

        # Fallback pure-Python path converts mappings and sequences
        saved_clean = ser_mod._accel_is_json_clean
        try:
            ser_mod._accel_is_json_clean = None
            py_dict = to_jsonable(clean_dict)
            self.assertEqual(py_dict, clean_dict)
        finally:
            ser_mod._accel_is_json_clean = saved_clean
