# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import pathlib
import sys
import unittest
from unittest.mock import patch

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import setup_notebook
from gunz_utils.ext import project_gitpython as project_module


class TestSetupNotebook(unittest.TestCase):
    def setUp(self):
        self.original_root = project_module._PROJECT_ROOT
        self.original_anchor = project_module._PROJECT_ANCHOR
        project_module._PROJECT_ROOT = None
        project_module._PROJECT_ANCHOR = None

    def tearDown(self):
        project_module._PROJECT_ROOT = self.original_root
        project_module._PROJECT_ANCHOR = self.original_anchor

    def test_returns_root_and_injects_src(self):
        root = setup_notebook(autoreload=False)
        self.assertIsInstance(root, pathlib.Path)
        self.assertIn(str(root / "src"), sys.path)

    def test_enables_autoreload_when_ipython_present(self):
        fake_ipython = unittest.mock.MagicMock()
        with patch(
            "gunz_utils.notebook.get_ipython",
            return_value=fake_ipython,
        ) as mock_get:
            setup_notebook(autoreload=True)
        mock_get.assert_called_once()
        fake_ipython.run_line_magic.assert_any_call("load_ext", "autoreload")
        fake_ipython.run_line_magic.assert_any_call("autoreload", "2")

    def test_no_ipython_is_noop(self):
        with patch("gunz_utils.notebook.get_ipython", return_value=None):
            root = setup_notebook(autoreload=True)
        self.assertIsInstance(root, pathlib.Path)


if __name__ == "__main__":
    unittest.main()
