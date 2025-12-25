# -*- coding: utf-8 -*-
import unittest
from gunz_utils.enums import BaseStrEnum, BaseIntEnum

class TestEnumSecurity(unittest.TestCase):
    def test_str_enum_length_limit(self):
        """Test that BaseStrEnum rejects overly long inputs."""
        class TestStr(BaseStrEnum):
            A = "a"

        # Limit is 1024.
        # Test just below, at, and above.

        # This assumes the implementation uses _MAX_INPUT_LENGTH = 1024
        limit = 1024

        # Valid length (should not raise ValueError for length, though it will raise for not found)
        # We catch the ValueError and check the message to distinguish
        long_str_ok = "a" * limit
        try:
            TestStr.from_fuzzy_string(long_str_ok)
        except ValueError as e:
            self.assertNotIn("Input string too long", str(e))

        # Invalid length
        long_str_bad = "a" * (limit + 1)
        with self.assertRaises(ValueError) as cm:
            TestStr.from_fuzzy_string(long_str_bad)
        self.assertIn("Input string too long", str(cm.exception))

    def test_int_enum_length_limit(self):
        """Test that BaseIntEnum rejects overly long inputs."""
        class TestInt(BaseIntEnum):
            ONE = 1

        limit = 1024

        # Valid length
        long_str_ok = "1" * limit
        try:
            TestInt.from_fuzzy_int_string(long_str_ok)
        except ValueError as e:
             # It might fail conversion to int if it's huge, or fail lookup
             # But it should NOT fail with our specific length error
            self.assertNotIn("Input string too long", str(e))

        # Invalid length
        long_str_bad = "1" * (limit + 1)
        with self.assertRaises(ValueError) as cm:
            TestInt.from_fuzzy_int_string(long_str_bad)
        self.assertIn("Input string too long", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
