"""Tests for safe primitive parsing utilities."""

from __future__ import annotations

import math
import unittest

from gunz_utils import parse_bool, safe_bool, safe_float, safe_int


class TestSafeInt(unittest.TestCase):
    def test_integer_string(self) -> None:
        self.assertEqual(safe_int("42"), 42)

    def test_whitespace(self) -> None:
        self.assertEqual(safe_int("  42  "), 42)

    def test_float_string_is_rejected(self) -> None:
        self.assertIsNone(safe_int("3.14"))

    def test_invalid_default(self) -> None:
        self.assertEqual(safe_int("abc", default=0), 0)

    def test_minimum_bound(self) -> None:
        self.assertIsNone(safe_int("-1", min=0))

    def test_maximum_bound(self) -> None:
        self.assertIsNone(safe_int("100", max=50))

    def test_bounds_accept_value(self) -> None:
        self.assertEqual(safe_int("100", min=0, max=200), 100)

    def test_alternate_base(self) -> None:
        self.assertEqual(safe_int("ff", base=16), 255)


class TestSafeFloat(unittest.TestCase):
    def test_float_string(self) -> None:
        self.assertEqual(safe_float("3.14"), 3.14)

    def test_whitespace(self) -> None:
        self.assertEqual(safe_float("  3.14  "), 3.14)

    def test_invalid_default(self) -> None:
        self.assertEqual(safe_float("abc", default=1.5), 1.5)

    def test_minimum_bound(self) -> None:
        self.assertIsNone(safe_float("-1.0", min=0.0))

    def test_maximum_bound(self) -> None:
        self.assertIsNone(safe_float("100.0", max=50.0))

    def test_infinity_allowed_by_default(self) -> None:
        self.assertTrue(math.isinf(safe_float("inf")))

    def test_infinity_can_be_rejected(self) -> None:
        self.assertIsNone(safe_float("inf", allow_inf=False))

    def test_nan_requires_opt_in(self) -> None:
        self.assertIsNone(safe_float("nan"))
        self.assertTrue(math.isnan(safe_float("nan", allow_nan=True)))


class TestSafeBool(unittest.TestCase):
    def test_bool_values(self) -> None:
        self.assertTrue(safe_bool(True))
        self.assertFalse(safe_bool(False))

    def test_integer_forms(self) -> None:
        self.assertTrue(safe_bool(1))
        self.assertFalse(safe_bool(0))

    def test_true_string_forms(self) -> None:
        for value in ("1", "true", "t", "yes", "y", "on"):
            with self.subTest(value=value):
                self.assertTrue(safe_bool(value))

    def test_false_string_forms(self) -> None:
        for value in ("0", "false", "f", "no", "n", "off"):
            with self.subTest(value=value):
                self.assertFalse(safe_bool(value))

    def test_case_insensitive(self) -> None:
        self.assertTrue(safe_bool(" YeS "))
        self.assertFalse(safe_bool(" OFF "))

    def test_whitespace(self) -> None:
        self.assertTrue(safe_bool("  on  "))

    def test_unrecognized_default(self) -> None:
        self.assertIsNone(safe_bool("maybe"))
        self.assertFalse(safe_bool("maybe", default=False))

    def test_type_mismatch(self) -> None:
        self.assertEqual(safe_bool(2, default=True), True)
        self.assertIsNone(safe_bool(None))


class TestParseBool(unittest.TestCase):
    def test_bool_values(self) -> None:
        self.assertTrue(parse_bool(True))
        self.assertFalse(parse_bool(False))

    def test_integer_forms(self) -> None:
        self.assertTrue(parse_bool(1))
        self.assertFalse(parse_bool(0))

    def test_true_string_forms(self) -> None:
        for value in ("1", "true", "t", "yes", "y", "on"):
            with self.subTest(value=value):
                self.assertTrue(parse_bool(value))

    def test_false_string_forms(self) -> None:
        for value in ("0", "false", "f", "no", "n", "off"):
            with self.subTest(value=value):
                self.assertFalse(parse_bool(value))

    def test_case_insensitive(self) -> None:
        self.assertTrue(parse_bool(" TrUe "))
        self.assertFalse(parse_bool(" FaLsE "))

    def test_whitespace(self) -> None:
        self.assertTrue(parse_bool("  yes  "))

    def test_unrecognized_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_bool("maybe")

    def test_type_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_bool(2)


if __name__ == "__main__":
    unittest.main()
