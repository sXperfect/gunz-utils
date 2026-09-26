from __future__ import annotations

import unittest
import warnings

from gunz_utils.benchmark import default_sampler
from gunz_utils.deprecation import GunzDeprecationWarning, deprecated


class TestPortabilityAndDeprecation(unittest.TestCase):
    def test_sampler_capabilities_are_explicit(self) -> None:
        capabilities = default_sampler().capabilities
        self.assertIsInstance(capabilities.rss, bool)
        self.assertIsInstance(capabilities.process_tree, bool)

    def test_deprecation_warning(self) -> None:
        @deprecated("old_api is deprecated; use new_api")
        def old_api() -> int:
            return 3

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertEqual(old_api(), 3)
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, GunzDeprecationWarning)


if __name__ == "__main__":
    unittest.main()
