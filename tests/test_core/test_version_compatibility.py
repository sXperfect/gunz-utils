"""Regression tests for package/module version and maintainer metadata compatibility."""

from __future__ import annotations

import importlib
import importlib.metadata
import tomllib
from pathlib import Path

import gunz_utils

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_VERSION_COMPAT_MODULES = (
    "gunz_utils.dict_utils",
    "gunz_utils.ext.observability_loguru",
    "gunz_utils.ext.project_stdlib",
    "gunz_utils.ext.secure_crypto",
    "gunz_utils.ext.secure_store",
    "gunz_utils.ext.validation_stdlib",
    "gunz_utils.formatting",
    "gunz_utils.hashing",
    "gunz_utils.io",
    "gunz_utils.iteration",
    "gunz_utils.models",
    "gunz_utils.parsing",
    "gunz_utils.redaction",
    "gunz_utils.timing",
    "gunz_utils.upstream_protocol",
)


def test_package_version_matches_installed_distribution() -> None:
    try:
        installed_version = importlib.metadata.version("gunz-utils")
    except importlib.metadata.PackageNotFoundError:
        import unittest

        raise unittest.SkipTest(
            "gunz-utils distribution metadata not installed in ambient environment"
        )
    assert gunz_utils.__version__ == installed_version


def test_historical_module_versions_match_package_version() -> None:
    for module_name in _VERSION_COMPAT_MODULES:
        try:
            module = importlib.import_module(module_name)
        except (ImportError, ModuleNotFoundError):
            continue
        assert module.__version__ == gunz_utils.__version__, module_name


def test_pyproject_uses_preferred_maintainer_email() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    assert project["authors"][0]["email"] == "yeremiag@gmail.com"


def test_legacy_maintainer_email_is_absent_from_repository_text() -> None:
    old_email = "adhisant@tnt.uni-hannover.de"
    candidates = [
        PROJECT_ROOT / "AGENTS.md",
        PROJECT_ROOT / "CONTRIBUTING.md",
        PROJECT_ROOT / "LICENSE.md",
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "CHANGELOG.md",
        PROJECT_ROOT / "pyproject.toml",
    ]
    for directory, patterns in (
        (PROJECT_ROOT / "src", ("*.py",)),
        (PROJECT_ROOT / "docs", ("*.md", "*.rst", "*.py")),
    ):
        for pattern in patterns:
            candidates.extend(directory.rglob(pattern))

    offenders = []
    for path in candidates:
        if path.is_file() and old_email in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []
