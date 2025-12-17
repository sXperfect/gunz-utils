import unittest
from gunz_utils.enums import BaseStrEnum, OptionalBaseStrEnum, BaseIntEnum

class TestBaseStrEnum(unittest.TestCase):
    def setUp(self):
        class Color(BaseStrEnum):
            # _ignore_ = ["ALIASES"] # No longer needed with __ALIASES__
            __ALIASES__ = {"dark": "dark_blue", "crimson": "red"}
            RED = "red"
            BLUE = "blue"
            DARK_BLUE = "dark_blue"
            LIGHT_GREEN = "light green"

        self.EnumClass = Color

    def test_basic_lookup_direct(self):
        self.assertEqual(self.EnumClass("red"), self.EnumClass.RED)
        self.assertEqual(self.EnumClass("blue"), self.EnumClass.BLUE)

    def test_from_fuzzy_string_case_insensitivity(self):
        self.assertEqual(self.EnumClass.from_fuzzy_string("RED"), self.EnumClass.RED)
        self.assertEqual(self.EnumClass.from_fuzzy_string("Blue"), self.EnumClass.BLUE)

    def test_from_fuzzy_string_separator_insensitivity(self):
        self.assertEqual(self.EnumClass.from_fuzzy_string("light-green"), self.EnumClass.LIGHT_GREEN)
        self.assertEqual(self.EnumClass.from_fuzzy_string("light_green"), self.EnumClass.LIGHT_GREEN)
        self.assertEqual(self.EnumClass.from_fuzzy_string("LIGHT GREEN"), self.EnumClass.LIGHT_GREEN)

    def test_from_fuzzy_string_aliases(self):
        self.assertEqual(self.EnumClass.from_fuzzy_string("dark"), self.EnumClass.DARK_BLUE)
        self.assertEqual(self.EnumClass.from_fuzzy_string("crimson"), self.EnumClass.RED)

    def test_introspection(self):
        self.assertEqual(self.EnumClass.names(), ["RED", "BLUE", "DARK_BLUE", "LIGHT_GREEN"])
        self.assertEqual(self.EnumClass.values(), ["red", "blue", "dark_blue", "light green"])
        self.assertEqual(self.EnumClass.items(), [
            ("RED", "red"),
            ("BLUE", "blue"),
            ("DARK_BLUE", "dark_blue"),
            ("LIGHT_GREEN", "light green")
        ])
        self.assertEqual(self.EnumClass.choices(), ["red", "blue", "dark_blue", "light green"])

    def test_get_or_none_exact_match(self):
        self.assertEqual(self.EnumClass.get_or_none("red"), self.EnumClass.RED)
    
    def test_get_or_none_fuzzy_match(self):
        self.assertEqual(self.EnumClass.get_or_none("dark"), self.EnumClass.DARK_BLUE)

    def test_get_or_none_no_match(self):
        self.assertIsNone(self.EnumClass.get_or_none("purple"))
        self.assertIsNone(self.EnumClass.get_or_none(123))

    def test_from_fuzzy_string_invalid_lookup(self):
        with self.assertRaises(ValueError):
            self.EnumClass.from_fuzzy_string("purple")


class TestOptionalBaseStrEnum(unittest.TestCase):
    def test_none_handling_get_or_none(self):
        class Status(OptionalBaseStrEnum):
            NONE = "none"
            ACTIVE = "active"

        self.assertEqual(Status.get_or_none(None), Status.NONE)
        self.assertEqual(Status.get_or_none("active"), Status.ACTIVE)
        self.assertEqual(Status.get_or_none("none"), Status.NONE)
        self.assertIsNone(Status.get_or_none("inactive"))

    def test_none_handling_direct_constructor(self):
        class Status(OptionalBaseStrEnum):
            NONE = "none"
            ACTIVE = "active"
        
        self.assertEqual(Status(None), Status.NONE)


    def test_missing_none_member(self):
        with self.assertRaises(TypeError):
            class BadStatus(OptionalBaseStrEnum):
                ACTIVE = "active"


class TestBaseIntEnum(unittest.TestCase):
    def setUp(self):
        class ErrorCode(BaseIntEnum):
            # _ignore_ = ["ALIASES"]
            __ALIASES__ = {"missing": 404, "ok": 200}
            OK = 200
            NOT_FOUND = 404

        self.EnumClass = ErrorCode

    def test_basic_lookup_direct(self):
        self.assertEqual(self.EnumClass(200), self.EnumClass.OK)
        self.assertEqual(self.EnumClass(404), self.EnumClass.NOT_FOUND)

    def test_from_fuzzy_int_string_aliases(self):
        self.assertEqual(self.EnumClass.from_fuzzy_int_string("missing"), self.EnumClass.NOT_FOUND)
        self.assertEqual(self.EnumClass.from_fuzzy_int_string("ok"), self.EnumClass.OK)

    def test_from_fuzzy_int_string_name_match(self):
        self.assertEqual(self.EnumClass.from_fuzzy_int_string("NOT_FOUND"), self.EnumClass.NOT_FOUND)
        self.assertEqual(self.EnumClass.from_fuzzy_int_string("not_found"), self.EnumClass.NOT_FOUND)

    def test_from_fuzzy_int_string_int_string_conversion(self):
        self.assertEqual(self.EnumClass.from_fuzzy_int_string("200"), self.EnumClass.OK)
        self.assertEqual(self.EnumClass.from_fuzzy_int_string("404"), self.EnumClass.NOT_FOUND)

    def test_from_fuzzy_int_string_invalid_lookup(self):
        with self.assertRaises(ValueError):
            self.EnumClass.from_fuzzy_int_string("500")
        with self.assertRaises(ValueError):
            self.EnumClass.from_fuzzy_int_string("bad_request")

    def test_get_or_none_exact_match(self):
        self.assertEqual(self.EnumClass.get_or_none(200), self.EnumClass.OK)

    def test_get_or_none_fuzzy_match(self):
        self.assertEqual(self.EnumClass.get_or_none("missing"), self.EnumClass.NOT_FOUND)
        self.assertEqual(self.EnumClass.get_or_none("ok"), self.EnumClass.OK)
        self.assertEqual(self.EnumClass.get_or_none("200"), self.EnumClass.OK)

    def test_get_or_none_no_match(self):
        self.assertIsNone(self.EnumClass.get_or_none(500))
        self.assertIsNone(self.EnumClass.get_or_none("unknown_error"))
        self.assertIsNone(self.EnumClass.get_or_none(None))

if __name__ == "__main__":
    unittest.main()