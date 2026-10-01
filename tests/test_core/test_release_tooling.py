"""Tests for the repository-local release tooling."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.policy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE_PY = PROJECT_ROOT / "scripts" / "release.py"


def _load_release_module():
    spec = importlib.util.spec_from_file_location("gunz_release", RELEASE_PY)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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
    (tmp_path / "src" / "gunz_utils" / "_version.py").write_text(
        "from importlib import metadata\n"
        '__version__ = metadata.version("gunz-utils")\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "gunz_utils" / "__init__.py").write_text(
        "def _resolve_package_version():\n"
        "    from ._version import __version__\n"
        "    return __version__\n"
        "__version__ = _resolve_package_version()\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "source" / "conf.py").write_text(
        "from importlib.metadata import version as package_version\n"
        'release = package_version("gunz-utils")\n',
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
    assert any(
        "example.py contains a package __version__ literal" in item
        for item in result.errors
    )


def test_prepare_auto_resolves_minimum_valid_target(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    fragment = tmp_path / "changes" / "feature.added.md"
    fragment.write_text("Add new feature.", encoding="utf-8")

    assert repo.prepare("auto") == 0

    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "1.11.0"' in pyproject
    assert not fragment.exists()
    assert repo.verify() == 0


def test_prepare_dry_run_does_not_modify_files_or_unlink_fragments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _fixture_repo(tmp_path)
    fragment = tmp_path / "changes" / "fix.fixed.md"
    fragment.write_text("Fix a small bug.", encoding="utf-8")

    pyproject_before = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    changelog_before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    assert repo.prepare("auto", dry_run=True) == 0

    captured = capsys.readouterr()
    assert "[DRY-RUN]" in captured.out
    assert "Target version: 1.10.1" in captured.out
    assert "fix.fixed.md" in captured.out

    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == pyproject_before
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == changelog_before
    assert fragment.exists()


def test_notes_extracts_specified_and_current_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _fixture_repo(tmp_path)
    assert repo.notes("1.10.0") == 0
    captured = capsys.readouterr()
    assert "- Previous release." in captured.out

    assert repo.notes() == 0
    captured_default = capsys.readouterr()
    assert "- Previous release." in captured_default.out


def test_unreleased_renders_pending_fragments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _fixture_repo(tmp_path)
    (tmp_path / "changes" / "f1.fixed.md").write_text("Fix crash.", encoding="utf-8")
    assert repo.unreleased() == 0
    captured = capsys.readouterr()
    assert "### Fixed" in captured.out
    assert "- Fix crash." in captured.out


def test_new_fragment_creates_properly_formatted_file(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    status = repo.new_fragment(
        category="security",
        message="Harden input validation",
        identifier="sec-1",
    )
    assert status == 0
    created = tmp_path / "changes" / "sec-1.security.md"
    assert created.is_file()
    assert created.read_text(encoding="utf-8") == "- Harden input validation\n"


def test_check_rejects_unresolved_conflict_markers(tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    fragment = tmp_path / "changes" / "conflict.fixed.md"
    fragment.write_text(
        "<<<<<<< HEAD\nFix a bug.\n=======\nFix bug differently.\n>>>>>>> branch\n",
        encoding="utf-8",
    )

    result = repo.check()
    assert not result.ok
    assert any("conflict marker" in err for err in result.errors)


def test_repository_release_metadata_is_self_consistent() -> None:
    repo = release.ReleaseRepo(PROJECT_ROOT)
    result = repo.check()
    assert result.ok, result.errors


