# -*- coding: utf-8 -*-
import unittest
from gunz_utils.security import sanitize_filename

class TestSecurityReserved(unittest.TestCase):
    def test_sanitize_filename_reserved_with_empty_replacement(self):
        """
        Test that sanitize_filename handles Windows reserved names even if replacement is empty.
        Previously, this returned the reserved name as-is (e.g. "CON").
        """
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved_names:
            # If replacement is empty, we expect the function to use a fallback (e.g. "_")
            # or simply prepend something to make it safe.
            # We'll assert that the result is NOT equal to the input name.
            sanitized = sanitize_filename(name, replacement="")
            self.assertNotEqual(sanitized.upper(), name)
            # It should probably be "_CON" or similar
            self.assertTrue(sanitized.startswith("_") or len(sanitized) > len(name))

    def test_sanitize_filename_reserved_with_valid_replacement(self):
        self.assertEqual(sanitize_filename("CON", replacement="-"), "-CON")

if __name__ == "__main__":
    unittest.main()
