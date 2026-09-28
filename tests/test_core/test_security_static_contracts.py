"""Static security invariants applied to every package source file."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = PROJECT_ROOT / "src" / "gunz_utils"

_BANNED_IMPORT_ROOTS = {"marshal", "pickle", "shelve"}
_BANNED_CALLS = {
    ("os", "popen"),
    ("os", "system"),
    ("subprocess", "getoutput"),
    ("subprocess", "getstatusoutput"),
    ("tempfile", "mktemp"),
    ("yaml", "load"),
    ("yaml", "unsafe_load"),
}


def _qualified_name(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


def _source_files() -> list[Path]:
    return sorted(PACKAGE_DIR.rglob("*.py"))


def test_all_package_sources_parse() -> None:
    files = _source_files()
    assert files
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_package_sources_avoid_code_execution_and_unsafe_deserialization() -> None:
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(PROJECT_ROOT)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in _BANNED_IMPORT_ROOTS:
                        offenders.append(f"{relative}:{node.lineno}: import {root}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in _BANNED_IMPORT_ROOTS:
                    offenders.append(f"{relative}:{node.lineno}: import {root}")
            elif isinstance(node, ast.Call):
                name = _qualified_name(node.func)
                if name in {("eval",), ("exec",)}:
                    offenders.append(f"{relative}:{node.lineno}: {name[0]}()")
                if name is not None and tuple(name[-2:]) in _BANNED_CALLS:
                    offenders.append(
                        f"{relative}:{node.lineno}: {'.'.join(name)}()"
                    )
                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        offenders.append(
                            f"{relative}:{node.lineno}: shell=True"
                        )

    assert offenders == []


def test_package_sources_do_not_use_assert_for_runtime_validation() -> None:
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(PROJECT_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                offenders.append(f"{relative}:{node.lineno}: assert")
    assert offenders == []


def test_package_sources_do_not_disable_tls_verification() -> None:
    offenders: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(PROJECT_ROOT)

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                name = _qualified_name(node)
                if name == ("ssl", "_create_unverified_context"):
                    offenders.append(
                        f"{relative}:{node.lineno}: ssl._create_unverified_context"
                    )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    name = _qualified_name(target)
                    if (
                        name is not None
                        and name[-1] == "check_hostname"
                        and isinstance(node.value, ast.Constant)
                        and node.value.value is False
                    ):
                        offenders.append(
                            f"{relative}:{node.lineno}: check_hostname=False"
                        )
            elif isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "verify"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is False
                    ):
                        offenders.append(
                            f"{relative}:{node.lineno}: verify=False"
                        )

    assert offenders == []
