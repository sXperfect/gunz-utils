"""Tests for Wave 7: enums, sentinels, and extensions (#84–#92)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import copy
import inspect
import pathlib
import unittest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.enums import BaseIntEnum, BaseStrEnum
from gunz_utils.ext.project_stdlib import resolve_project_root
from gunz_utils.ext.validation_stdlib import type_checked
from gunz_utils.sentinels import UNSET, UnsetType, default_factory


class Color(BaseStrEnum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class Status(BaseIntEnum):
    OK = 200
    NOT_FOUND = 404
    SERVER_ERROR = 500


class TestWave7Enums(unittest.TestCase):
    def test_item84_str_enum_whitespace_stripping(self) -> None:
        self.assertIs(Color.from_fuzzy_string("  red  "), Color.RED)
        self.assertIs(Color.from_fuzzy_string(" BLUE "), Color.BLUE)

    def test_item85_int_enum_string_integer_parsing(self) -> None:
        self.assertIs(Status.from_fuzzy_int_string(" 200 "), Status.OK)
        self.assertIs(Status.from_fuzzy_int_string("404"), Status.NOT_FOUND)

    def test_item86_bounded_error_string_reflection(self) -> None:
        with self.assertRaises(ValueError) as cm:
            Color.from_fuzzy_string("unknown_color_xyz")
        err_msg = str(cm.exception)
        self.assertIn("unknown_color_xyz", err_msg)
        self.assertIn("red", err_msg)


class TestWave7Sentinels(unittest.TestCase):
    def test_item87_unset_slots_and_singleton(self) -> None:
        self.assertEqual(UnsetType.__slots__, ())
        self.assertFalse(hasattr(UNSET, "__dict__"))
        self.assertIs(copy.copy(UNSET), UNSET)
        self.assertIs(copy.deepcopy(UNSET), UNSET)

        #? default_factory
        called = False

        def factory() -> str:
            nonlocal called
            called = True
            return "computed"

        with self.assertRaises(TypeError):
            default_factory(UNSET, "not-callable")  # type: ignore[arg-type]

        self.assertEqual(default_factory(UNSET, factory), "computed")
        self.assertTrue(called)

        called = False
        self.assertEqual(default_factory("existing", factory), "existing")
        self.assertFalse(called)


class TestWave7ValidationStdlib(unittest.IsolatedAsyncioTestCase):
    def test_item88_pep484_int_for_float_and_bool_rejection(self) -> None:
        @type_checked
        def compute_ratio(
            val: float,
        ) -> float:
            return val * 2.0

        #? float is valid
        self.assertEqual(compute_ratio(2.5), 5.0)
        #? int for float is valid under PEP 484
        self.assertEqual(compute_ratio(3), 6.0)
        #? bool is rejected for float
        with self.assertRaises(TypeError):
            compute_ratio(True)

    async def test_item89_coroutine_function_preservation(self) -> None:
        @type_checked
        async def fetch_data(
            name: str,
        ) -> str:
            return f"data-{name}"

        #? iscoroutinefunction must remain True!
        self.assertTrue(inspect.iscoroutinefunction(fetch_data))
        res = await fetch_data("abc")
        self.assertEqual(res, "data-abc")

        with self.assertRaises(TypeError):
            await fetch_data(123)  # type: ignore[arg-type]


class TestWave7Project(unittest.TestCase):
    def test_item90_file_anchor_and_bare_string_rejection(self) -> None:
        with self.assertRaises(TypeError):
            resolve_project_root(subpaths="bare string")  # type: ignore[arg-type]

        #? Anchor as current file
        root = resolve_project_root(
    anchor=pathlib.Path(__file__),
     inject_to_sys_path=False)
        self.assertTrue(root.is_dir())
        self.assertTrue((root / "pyproject.toml").exists() or (root / ".git").exists())


if __name__ == "__main__":
    unittest.main()
