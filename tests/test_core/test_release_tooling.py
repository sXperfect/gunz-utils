"""Tests for the repository-local release tooling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_PY = PROJECT_ROOT / "scripts" / "release.py"


def _load_release_module():
    spec = importlib.util.spec_from_file_location("gunz_release", RELEASE_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load_release_module()


def _fixture_repo(tmp_path: Path):
    (tmp_path / "changes").mkdir()
    (tmp_path / "src" / "gunz_utils").mkdir(parents=True)
    (tmp_path / "docs" / "source").mkdir(parents=True)

    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "gunz-utils"
version = "1.10.0"
description = "fixture"

[project.optional-dependencies]
docs = []
""",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        """# Changelog

## [Unreleased]

Pending fragments are stored separately.

## [1.10.0] — 2026-09-27

- Previous release.
""",
        encoding="utf-8",
    )
    (tmp_path / "src" / "gunz_utils" / "__init__.py").write_text(
        'from importlib.metadata import version\n'
        '__version__ = version("gunz-utils")\n',
        encoding="utf-8",
    )
    (tmp_path / "docs" / "source" / "conf.py").write_text(
        'from importlib.metadata import version\n'
        'release = version("gunz-utils")\n',
        encoding="utf-8",
    )
    return release.ReleaseRepo(tmp_path)


def test_semver_is_strict() -> None:
    assert str(release.SemVer.parse("1.2.3")) == "1.2.3"
    for invalid in ("1.2", "v1.2.3", "01.2.3", "1.2.3-rc1"):
        with pytest.raises(release.ReleaseError):
            release.SemVer.parse(invalid)


def test_required_bump_uses_strongest_fragment(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    (tmp_path / "changes" / "a.fixed.md").write_text("Fix a bug.", encoding="utf-8")
    (tmp_path / "changes" / "b.added.md").write_text("Add an API.", encoding="utf-8")
    (tmp_path / "changes" / "c.breaking.md").write_text(
        "Remove an API.", encoding="utf-8"
    )

    assert repo.required_bump(repo.fragments()) == "major"
    assert repo.minimum_target(release.SemVer.parse("1.10.0"), "major") == (
        release.SemVer.parse("2.0.0")
    )


def test_duplicate_fragment_ids_are_rejected(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    (tmp_path / "changes" / "same.added.md").write_text("Add.", encoding="utf-8")
    (tmp_path / "changes" / "same.fixed.md").write_text("Fix.", encoding="utf-8")

    with pytest.raises(release.ReleaseError, match="duplicate fragment id"):
        repo.fragments()


def test_prepare_enforces_breaking_major_and_preserves_toml(
    tmp_path: Path,
) -> None:
    repo = _fixture_repo(tmp_path)
    fragment = tmp_path / "changes" / "remove-module-version.breaking.md"
    fragment.write_text("Remove legacy module version attributes.", encoding="utf-8")

    with pytest.raises(release.ReleaseError, match="minimum allowed target is 2.0.0"):
        repo.prepare("1.11.0")

    assert repo.prepare("2.0.0") == 0

    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "2.0.0"\ndescription = "fixture"' in pyproject
    assert "[project.optional-dependencies]\ndocs = []" in pyproject

    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [2.0.0]" in changelog
    assert "### Breaking" in changelog
    assert "- Remove legacy module version attributes." in changelog
    assert not fragment.exists()
    assert repo.verify() == 0


def test_check_rejects_module_version_literals(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    module = tmp_path / "src" / "gunz_utils" / "example.py"
    module.write_text('__version__ = "9.9.9"\n', encoding="utf-8")

    result = repo.check()
    assert not result.ok
    assert any("example.py contains a package __version__ literal" in item for item in result.errors)


def test_repository_release_metadata_is_self_consistent() -> None:
    repo = release.ReleaseRepo(PROJECT_ROOT)
    result = repo.check()
    assert result.ok, result.errors
