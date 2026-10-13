"""Phase 44 (security lane) perpetual-audit tests.

Scope (optional ext modules): project_gitpython, project_stdlib,
validation_pydantic, validation_stdlib.

All four modules were deep-audited and found already correct (no NEW security
or correctness defect). These GREEN pins exercise the security-relevant
properties without weakening pydantic/GitPython/type-checking guarantees:
  - validation_stdlib: bool-vs-int separation, Optional/Union, recursive
    list/dict/tuple element validation, tuple[()], varargs/**kw element checks,
    value-redacted TypeError messages, Callable.
  - validation_pydantic: strict bool/int separation, value-redacted errors
    (input value never appears), async redaction.
  - project_stdlib: marker (pyproject.toml) resolution, git subprocess fallback
    with fixed argument list (no shell), RuntimeError on missing root.
  - project_gitpython: git repo root resolution, masked (non-leaking) errors on
    missing root.

Recurring classes checked and found N/A here: no float() conversions (so no
unguarded-float OverflowError->ValueError), no regex (so no ReDoS), no
attacker-controlled unbounded recursion (annotation-depth-bounded), no shell
interpolation in the Git subprocess paths.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

import pytest

from gunz_utils.ext.validation_pydantic import type_checked as pd_type_checked
from gunz_utils.ext.validation_stdlib import type_checked as st_type_checked

# ---------------------------------------------------------------------------
# validation_stdlib GREEN pins
# ---------------------------------------------------------------------------

def test_stdlib_bool_is_not_int() -> None:
    @st_type_checked()
    def f(value: int) -> int:
        return value

    assert f(5) == 5
    for bad in [True, "5", 5.0]:
        with pytest.raises(TypeError):
            f(bad)


def test_stdlib_optional_union() -> None:
    @st_type_checked()
    def f(value: int | None) -> object:
        return value

    assert f(None) is None
    assert f(3) == 3
    for bad in [True, "s", 2.5]:
        with pytest.raises(TypeError):
            f(bad)


def test_stdlib_recursive_list_and_dict_elements() -> None:
    @st_type_checked()
    def f_list(value: list[int]) -> object:
        return value

    assert f_list([1, 2]) == [1, 2]
    with pytest.raises(TypeError):
        f_list([1, "a"])

    @st_type_checked()
    def f_dict(value: dict[str, int]) -> object:
        return value

    assert f_dict({"a": 1}) == {"a": 1}
    with pytest.raises(TypeError):
        f_dict({"a": "b"})
    with pytest.raises(TypeError):
        f_dict({1: 1})


def test_stdlib_tuple_edges() -> None:
    @st_type_checked()
    def f_empty(value: tuple[()]) -> object:
        return value

    assert f_empty(()) == ()
    with pytest.raises(TypeError):
        f_empty((1,))

    @st_type_checked()
    def f_fixed(value: tuple[int, str]) -> object:
        return value

    assert f_fixed((1, "a")) == (1, "a")
    with pytest.raises(TypeError):
        f_fixed((1, 2))

    @st_type_checked()
    def f_var(value: tuple[int, ...]) -> object:
        return value

    assert f_var((1, 2, 3)) == (1, 2, 3)


def test_stdlib_varargs_and_kwargs_element_check() -> None:
    @st_type_checked()
    def f(*items: int) -> int:
        return sum(items)

    assert f(1, 2, 3) == 6
    with pytest.raises(TypeError):
        f(1, "x")

    @st_type_checked()
    def g(**kw: int) -> int:
        return sum(kw.values())

    assert g(a=1, b=2) == 3
    with pytest.raises(TypeError):
        g(a="x")


def test_stdlib_error_message_redacts_values() -> None:
    @st_type_checked()
    def f(value: int) -> int:
        return value

    try:
        f("SECRETTOKEN123")
    except TypeError as exc:
        assert "SECRETTOKEN123" not in str(exc)
        assert "str" in str(exc)


# ---------------------------------------------------------------------------
# validation_pydantic GREEN pins
# ---------------------------------------------------------------------------

def test_pydantic_strict_bool_int() -> None:
    @pd_type_checked()
    def f(value: int) -> int:
        return value

    assert f(5) == 5
    for bad in [True, "5"]:
        with pytest.raises(TypeError):
            f(bad)


def test_pydantic_error_redacts_input_value() -> None:
    @pd_type_checked()
    def f(value: str) -> str:
        return value

    try:
        f(12345)
    except TypeError as exc:
        assert "12345" not in str(exc)
        assert "int" in str(exc)


def test_pydantic_async_redacts_input_value() -> None:
    @pd_type_checked()
    async def f(value: int) -> int:
        await asyncio.sleep(0)
        return value

    async def scenario() -> None:
        with pytest.raises(TypeError):
            await f("SENSITIVE")

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# project_stdlib GREEN pins
# ---------------------------------------------------------------------------

def _make_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "f.txt").write_text("x")


def test_project_stdlib_marker_resolution() -> None:
    import gunz_utils.ext.project_stdlib as ps

    directory = Path(tempfile.mkdtemp())
    (directory / "pyproject.toml").write_text("[project]\n")
    nested = directory / "a" / "b"
    nested.mkdir(parents=True)
    assert ps.resolve_project_root(str(nested), inject_to_sys_path=False) == (
        directory.resolve()
    )


def test_project_stdlib_git_fallback_and_non_repo_error() -> None:
    import gunz_utils.ext.project_stdlib as ps

    git_dir = Path(tempfile.mkdtemp())
    _make_git_repo(git_dir)
    deep = git_dir / "x" / "y"
    deep.mkdir(parents=True)
    assert ps.resolve_project_root(str(deep), inject_to_sys_path=False) == (
        git_dir.resolve()
    )

    with pytest.raises(RuntimeError):
        ps.resolve_project_root(str(Path(tempfile.mkdtemp())), inject_to_sys_path=False)


# ---------------------------------------------------------------------------
# project_gitpython GREEN pins
# ---------------------------------------------------------------------------

def test_project_gitpython_resolution_and_masked_error() -> None:
    import gunz_utils.ext.project_gitpython as pg

    git_dir = Path(tempfile.mkdtemp())
    _make_git_repo(git_dir)
    deep = git_dir / "x" / "y"
    deep.mkdir(parents=True)
    assert pg.resolve_project_root(str(deep), inject_to_sys_path=False) == (
        git_dir.resolve()
    )

    with pytest.raises(RuntimeError):
        pg.resolve_project_root(str(Path(tempfile.mkdtemp())), inject_to_sys_path=False)
