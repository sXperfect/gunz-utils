import unittest
import pathlib
import sys
import tempfile
from gunz_utils.project import resolve_project_root, _PROJECT_ROOT
from gunz_utils import project as project_module


class TestProject(unittest.TestCase):
    def setUp(self):
        self.original_root = project_module._PROJECT_ROOT
        project_module._PROJECT_ROOT = None

    def tearDown(self):
        project_module._PROJECT_ROOT = self.original_root

    def test_resolve_project_root_finds_git_root(self):
        root = resolve_project_root()
        self.assertIsInstance(root, pathlib.Path)
        self.assertTrue((root / ".git").exists())

    def test_resolve_project_root_caching(self):
        root1 = resolve_project_root()
        root2 = resolve_project_root()
        self.assertEqual(root1, root2)

    def test_resolve_project_root_injects_to_sys_path(self):
        project_module._PROJECT_ROOT = None
        root = resolve_project_root(inject_to_sys_path=True)
        self.assertIn(str(root), sys.path)

    def test_resolve_project_root_no_inject(self):
        project_module._PROJECT_ROOT = None
        original_path = sys.path.copy()
        root = resolve_project_root(inject_to_sys_path=False)
        self.assertEqual(sys.path, original_path)

    def test_resolve_project_root_invalid_anchor(self):
        project_module._PROJECT_ROOT = None
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaisesRegex(RuntimeError, "Could not find project root"):
                resolve_project_root(anchor=tmpdir, inject_to_sys_path=False)

    def test_resolve_project_root_custom_anchor(self):
        project_module._PROJECT_ROOT = None
        root = resolve_project_root(anchor=".")
        self.assertIsInstance(root, pathlib.Path)


if __name__ == "__main__":
    import sys
    unittest.main()