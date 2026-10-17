# gunz-style: ignore-file[GS010,GS011]
"""Comprehensive release safety, workflow boundaries, and rollback contracts."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

pytestmark = pytest.mark.policy

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "scripts" / "release.py"


def _load_script(
    name: str,
) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"gunz_utils_test_{name}",
        ROOT / "scripts" / f"{name}.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load script {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _release(
    root: Path,
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RELEASE), "--root", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


@pytest.fixture
def release_repo(
    tmp_path: Path,
) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "gunz-utils"\nversion = "0.1.0"\n'
        '[tool.other]\nversion = "9.8.7"\n',
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\nEntries live in changes/.\n",
        encoding="utf-8",
    )
    (tmp_path / "changes").mkdir()
    source = tmp_path / "src" / "gunz_utils"
    source.mkdir(parents=True)
    (source / "_version.py").write_text(
        "from importlib import metadata\n"
        'try:\n    __version__ = metadata.version("gunz-utils")\n'
        'except metadata.PackageNotFoundError:\n    __version__ = "0+unknown"\n',
        encoding="utf-8",
    )
    return tmp_path


def _fragment(
    root: Path,
    name: str = "change.fixed.md",
    text: str = "Fix a bug.",
) -> Path:
    path = root / "changes" / name
    path.write_text(text, encoding="utf-8")
    return path


def _snapshot(
    root: Path,
) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


def _git(
    root: Path,
    *args: str,
) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release-test@example.invalid",
            *args,
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
    return result.stdout.strip()


def _git_release_repo(
    tmp_path: Path,
) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "gunz-utils"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\nEntries live in changes/.\n",
        encoding="utf-8",
    )
    (root / "changes").mkdir()
    source = root / "src" / "gunz_utils"
    source.mkdir(parents=True)
    (source / "x.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "base")
    _git(root, "checkout", "-q", "-b", "topic")
    return root


def test_release_check_is_offline_and_nonmutating(
    release_repo: Path,
) -> None:
    _fragment(release_repo)
    before = _snapshot(release_repo)
    result = _release(release_repo, "check")
    assert result.returncode == 0, result.stderr
    assert "No local release tags" in result.stdout
    assert _snapshot(release_repo) == before


def test_check_fragment_flags_src_change_without_fragment(
    tmp_path: Path,
) -> None:
    repo = _git_release_repo(tmp_path)
    (repo / "src" / "gunz_utils" / "x.py").write_text("VALUE = 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "change src without fragment")
    result = _release(repo, "check-fragment", "--base", "main")
    assert result.returncode == 1
    assert "without a changelog fragment" in result.stderr


def test_check_fragment_passes_when_fragment_added(
    tmp_path: Path,
) -> None:
    repo = _git_release_repo(tmp_path)
    (repo / "src" / "gunz_utils" / "x.py").write_text("VALUE = 2\n", encoding="utf-8")
    _fragment(repo, "change-src.fixed.md", "Fix source behavior.")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "change src with fragment")
    result = _release(repo, "check-fragment", "--base", "main")
    assert result.returncode == 0
    assert "changelog fragment coverage: OK" in result.stdout


def test_check_fragment_ignores_non_source_changes(
    tmp_path: Path,
) -> None:
    repo = _git_release_repo(tmp_path)
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "docs only")
    result = _release(repo, "check-fragment", "--base", "main")
    assert result.returncode == 0


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("no-category.md", "entry"),
        ("bad.unknown.md", "entry"),
        ("empty.fixed.md", "  \n"),
        ("conflict.fixed.md", "<<<<<<< ours\nentry\n=======\n"),
    ],
)
def test_release_rejects_invalid_fragments(
    release_repo: Path,
    name: str,
    text: str,
) -> None:
    _fragment(release_repo, name, text)
    assert _release(release_repo, "check").returncode != 0


@pytest.mark.parametrize(
    "heading",
    [
        "## [999.0.0]",
        "## [Unreleased]",
        "   ## Another release",
        "# Changelog",
        "Another release\n---",
        "Another release\n===",
    ],
)
def test_release_rejects_fragment_heading_injection_without_mutation(
    release_repo: Path,
    heading: str,
) -> None:
    text = f"- Fix a bug.\n\n{heading}\nInjected heading."
    before = _snapshot(release_repo)
    result = _release(
        release_repo, "new", "--id", "heading", "-c", "fixed", "-m", text
    )
    assert result.returncode != 0
    assert "unsupported release-level heading" in result.stderr
    assert _snapshot(release_repo) == before
    _fragment(release_repo, "heading.fixed.md", text)
    before = _snapshot(release_repo)
    for args in [("check",), ("prepare", "--dry-run"), ("prepare",)]:
        result = _release(release_repo, *args)
        assert result.returncode != 0
        assert "unsupported release-level heading" in result.stderr
        assert _snapshot(release_repo) == before


def test_release_rejects_duplicate_ids_across_categories(
    release_repo: Path,
) -> None:
    _fragment(release_repo, "same.fixed.md")
    result = _release(
        release_repo, "new", "--id", "same", "-c", "added", "-m", "Add feature."
    )
    assert result.returncode != 0
    assert not (release_repo / "changes" / "same.added.md").exists()
    _fragment(release_repo, "same.added.md")
    assert "duplicate fragment id" in _release(release_repo, "check").stderr.lower()


def test_release_rejects_independent_version_literals(
    release_repo: Path,
) -> None:
    path = release_repo / "src" / "gunz_utils" / "extra.py"
    path.write_text('__version__: str = "0.1.0"\n', encoding="utf-8")
    assert "independent __version__ literal" in _release(release_repo, "check").stderr


def test_release_dry_run_preserves_every_input(
    release_repo: Path,
) -> None:
    _fragment(release_repo, "feature.added.md", "Add the feature.")
    before = _snapshot(release_repo)
    result = _release(release_repo, "prepare", "auto", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert "0.2.0" in result.stdout
    assert _snapshot(release_repo) == before


@pytest.mark.parametrize("tooling_note", [False, True])
def test_release_preserves_manual_unreleased_notes_and_history(
    release_repo: Path,
    tooling_note: bool,
) -> None:
    module = _load_script("release")
    manual = (
        "    preserve_this_indentation()\n\n"
        "### Fixed\n\n- Important manually recorded change."
    )
    history = (
        "## [0.1.0] — 2026-09-01\n\n### Added\n\n- Existing release entry.\n"
    )
    prefix = module.UNRELEASED_NOTE + "\n\n" if tooling_note else ""
    (release_repo / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n" + prefix + manual + "\n\n" + history,
        encoding="utf-8",
    )
    _fragment(release_repo, text="Fix a different bug.")
    before = _snapshot(release_repo)
    preview = _release(release_repo, "prepare", "--dry-run")
    assert preview.returncode == 0, preview.stderr
    assert manual in preview.stdout
    assert "Fix a different bug." in preview.stdout
    assert module.UNRELEASED_NOTE not in preview.stdout
    assert _snapshot(release_repo) == before
    result = _release(release_repo, "prepare")
    assert result.returncode == 0, result.stderr
    changelog = (release_repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.endswith(history)
    assert changelog.count(manual) == 1
    assert changelog.index(manual) > changelog.index("## [0.1.1]")
    assert changelog.count(module.UNRELEASED_NOTE) == 1
    assert list((release_repo / "changes").iterdir()) == []
    assert _release(release_repo, "verify").returncode == 0
    notes = _release(release_repo, "notes").stdout
    assert "Important manually recorded change." in notes
    assert "Fix a different bug." in notes
    assert "Existing release entry." not in notes


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize(
    ("rendered", "error"),
    [
        ("- Entry.\n\n## [999.0.0]\n\nInjected.", "newer than"),
        ("- Entry.\n\n## [0.1.1]\n\nInjected.", "duplicate"),
        ("- Entry.\n\n## [0.0.1]\n\nInjected.", "exactly one release heading"),
        ("<<<<<<< ours\nEntry.\n=======\n", "unresolved conflict markers"),
    ],
)
def test_release_validates_rendered_changelog_before_any_mutation(
    release_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    dry_run: bool,
    rendered: str,
    error: str,
) -> None:
    module = _load_script("release")
    _fragment(release_repo)
    before = _snapshot(release_repo)
    repo = module.ReleaseRepo(release_repo)
    monkeypatch.setattr(repo, "render", lambda fragments: rendered)

    def reject_write(
        path: Path,
        text: str,
    ) -> None:
        raise AssertionError("candidate validation must happen before any write")

    monkeypatch.setattr(module, "atomic_write", reject_write)
    with pytest.raises(module.ReleaseError, match=error):
        repo.prepare(dry_run=dry_run)
    assert _snapshot(release_repo) == before


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize(
    ("candidate", "error"),
    [
        ('[project]\nversion = "0.1.0"\n', "does not match 0.1.1"),
        ("[project]\nversion = 17\n", "missing pyproject.toml"),
    ],
)
def test_release_validates_candidate_version_before_any_mutation(
    release_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    dry_run: bool,
    candidate: str,
    error: str,
) -> None:
    module = _load_script("release")
    _fragment(release_repo)
    before = _snapshot(release_repo)
    repo = module.ReleaseRepo(release_repo)
    monkeypatch.setattr(repo, "_updated_pyproject", lambda target: candidate)

    def reject_write(
        path: Path,
        text: str,
    ) -> None:
        raise AssertionError("candidate validation must happen before any write")

    monkeypatch.setattr(module, "atomic_write", reject_write)
    with pytest.raises(module.ReleaseError, match=error):
        repo.prepare(dry_run=dry_run)
    assert _snapshot(release_repo) == before


def test_release_enforces_minimum_and_consolidates_fragments(
    release_repo: Path,
) -> None:
    _fragment(release_repo, "feature.added.md", "Add the feature.")
    _fragment(
        release_repo,
        "private.internal.md",
        "Internal detail omitted from public notes.",
    )
    before = _snapshot(release_repo)
    assert _release(release_repo, "prepare", "0.1.1").returncode != 0
    assert _snapshot(release_repo) == before
    result = _release(release_repo, "prepare", "auto")
    assert result.returncode == 0, result.stderr
    data = tomllib.loads((release_repo / "pyproject.toml").read_text())
    assert data["project"]["version"] == "0.2.0"
    assert data["tool"]["other"]["version"] == "9.8.7"
    notes = (release_repo / "CHANGELOG.md").read_text()
    assert "## [0.2.0]" in notes and "Add the feature." in notes
    assert "Internal detail" not in notes
    assert list((release_repo / "changes").iterdir()) == []
    assert _release(release_repo, "verify").returncode == 0
    assert "Add the feature." in _release(release_repo, "notes").stdout


def test_pre_one_major_release_policy_is_explicit(
    release_repo: Path,
) -> None:
    _fragment(release_repo, "incompatible.breaking.md")
    result = _release(release_repo, "prepare", "auto", "--dry-run")
    assert result.returncode == 0
    assert "1.0.0" in result.stdout


def test_release_restores_metadata_when_fragment_removal_fails(
    release_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script("release")
    first = _fragment(release_repo, "first.fixed.md")
    failing = _fragment(release_repo, "second.fixed.md")
    before = _snapshot(release_repo)
    unlink = Path.unlink

    def fail_once(
        path: Path,
        *args: object,
        **kwargs: object,
    ) -> None:
        if path == failing:
            raise OSError("injected fragment removal failure")
        unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_once)
    with pytest.raises(OSError, match="injected fragment"):
        module.ReleaseRepo(release_repo).prepare()
    assert first.exists()
    assert _snapshot(release_repo) == before


def test_tag_requires_main_and_an_explicit_create_flag(
    release_repo: Path,
) -> None:
    _fragment(release_repo)
    assert _release(release_repo, "prepare", "auto").returncode == 0
    _git(release_repo, "init", "-b", "feature/release")
    _git(release_repo, "config", "user.name", "Release Test")
    _git(release_repo, "config", "user.email", "release-test@example.invalid")
    _git(release_repo, "add", ".")
    _git(release_repo, "commit", "-m", "chore(release): v0.1.1")
    _git(release_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert "requires the main branch" in _release(release_repo, "tag").stderr
    _git(release_repo, "branch", "-m", "main")
    assert _release(release_repo, "tag").returncode == 0
    assert _git(release_repo, "tag", "--list") == ""
    assert _release(release_repo, "tag", "--create").returncode == 0
    assert _git(release_repo, "cat-file", "-t", "refs/tags/v0.1.1") == "tag"
    assert _release(release_repo, "tag", "--create").returncode != 0
