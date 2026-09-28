import pathlib
import sys
import tempfile
import unittest

from git import Repo

from gunz_utils import resolve_project_root
from gunz_utils.ext import project_gitpython as project_module


class TestProject(unittest.TestCase):
    def setUp(self):
        self.original_root = project_module._PROJECT_ROOT
        self.original_anchor = project_module._PROJECT_ANCHOR
        project_module._PROJECT_ROOT = None
        project_module._PROJECT_ANCHOR = None

    def tearDown(self):
        project_module._PROJECT_ROOT = self.original_root
        project_module._PROJECT_ANCHOR = self.original_anchor

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
        project_module._PROJECT_ANCHOR = None
        original_path = sys.path.copy()
        root = resolve_project_root(inject_to_sys_path=False)
        self.assertEqual(sys.path, original_path)
        resolve_project_root(inject_to_sys_path=True)
        self.assertIn(str(root), sys.path)

    def test_cache_does_not_cross_project_anchors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            first = pathlib.Path(tmpdir) / "first"
            second = pathlib.Path(tmpdir) / "second"
            Repo.init(first)
            Repo.init(second)
            self.assertEqual(
                resolve_project_root(
                    str(first),
                    inject_to_sys_path=False,
                ),
                first.resolve(),
            )
            self.assertEqual(
                resolve_project_root(
                    str(second),
                    inject_to_sys_path=False,
                ),
                second.resolve(),
            )

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
