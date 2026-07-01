"""Tests for gunz_utils.ext.* stdlib fallback implementations.

These exercise the same public surface as the pydantic/gitpython
backends but without those runtime dependencies.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from gunz_utils.ext.validation_stdlib import type_checked as stdlib_type_checked
from gunz_utils.ext.project_stdlib import (
    resolve_project_root as stdlib_resolve_project_root,
)


class TestStdlibTypeChecked(unittest.TestCase):
    def test_basic_validation(self):
        @stdlib_type_checked
        def f(x: int):
            return x * 2

        self.assertEqual(f(3), 6)
        with self.assertRaises(TypeError):
            f("not-an-int")

    def test_error_message_format(self):
        @stdlib_type_checked
        def my_func(a: int):
            return a

        with self.assertRaises(TypeError) as cm:
            my_func("hello")
        msg = str(cm.exception)
        self.assertIn("Validation error in 'my_func'", msg)
        self.assertIn("Argument 'a'", msg)
        self.assertIn("got type 'str'", msg)

    def test_sensitive_data_not_leaked(self):
        sensitive_password = "P@ssw0rd!12345"

        @stdlib_type_checked
        def login(username: str, age: int):
            pass

        with self.assertRaises(TypeError) as cm:
            login("user", age=sensitive_password)

        msg = str(cm.exception)
        self.assertNotIn(sensitive_password, msg)
        self.assertIn("got type 'str'", msg)

    def test_varargs(self):
        @stdlib_type_checked
        def f(*args: int):
            return sum(args)

        self.assertEqual(f(1, 2, 3), 6)
        with self.assertRaises(TypeError):
            f(1, "two", 3)

    def test_kwargs(self):
        @stdlib_type_checked
        def f(**kw: str):
            return ",".join(f"{k}={v}" for k, v in sorted(kw.items()))

        self.assertEqual(f(a="1", b="2"), "a=1,b=2")
        with self.assertRaises(TypeError):
            f(a=1)


class TestStdlibResolveProjectRoot(unittest.TestCase):
    def setUp(self):
        from gunz_utils.ext import project_stdlib
        project_stdlib._PROJECT_ROOT = None
        self._tmpdir = tempfile.mkdtemp(prefix="gutils-stdlib-test-")
        self._saved_cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self._saved_cwd)
        subprocess.run(["rm", "-rf", self._tmpdir], check=False)
        from gunz_utils.ext import project_stdlib
        project_stdlib._PROJECT_ROOT = None

    def _make_repo(self, with_pyproject: bool = False) -> pathlib.Path:
        repo = pathlib.Path(self._tmpdir) / "myproj"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        if with_pyproject:
            (repo / "pyproject.toml").write_text("[project]\nname='x'\n")
        return repo.resolve()

    def test_finds_via_walk_up(self):
        repo = self._make_repo()
        os.chdir(str(repo))
        result = stdlib_resolve_project_root(inject_to_sys_path=False)
        self.assertEqual(result, repo)

    def test_finds_from_subdir(self):
        repo = self._make_repo()
        sub = repo / "src" / "pkg"
        sub.mkdir(parents=True)
        os.chdir(str(sub))
        result = stdlib_resolve_project_root(inject_to_sys_path=False)
        self.assertEqual(result, repo)

    def test_injects_into_sys_path(self):
        repo = self._make_repo()
        os.chdir(str(repo))
        original_path = list(sys.path)
        try:
            stdlib_resolve_project_root(inject_to_sys_path=True)
            self.assertEqual(sys.path[0], str(repo))
        finally:
            sys.path[:] = original_path

    def test_raises_outside_repo(self):
        os.chdir(self._tmpdir)
        with self.assertRaises(RuntimeError):
            stdlib_resolve_project_root(inject_to_sys_path=False)


if __name__ == "__main__":
    unittest.main()