from __future__ import annotations

import unittest

import gunz_utils


class TestPublicAPI(unittest.TestCase):
    def test_all_exports_resolve(self) -> None:
        missing = [name for name in gunz_utils.__all__ if not hasattr(gunz_utils, name)]
        self.assertEqual(missing, [])

    def test_all_exports_are_unique(self) -> None:
        self.assertEqual(len(gunz_utils.__all__), len(set(gunz_utils.__all__)))


if __name__ == "__main__":
    unittest.main()
