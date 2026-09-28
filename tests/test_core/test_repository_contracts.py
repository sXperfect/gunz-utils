"""Repository-level package, typing, and documentation contract tests."""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = PROJECT_ROOT / "src" / "gunz_utils"
API_REFERENCE = PROJECT_ROOT / "docs" / "source" / "api.rst"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _declares_public_all(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            declares_all = any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
            if declares_all:
                return True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                return True
    return False


def _documented_modules() -> set[str]:
    text = API_REFERENCE.read_text(encoding="utf-8")
    pattern = r"^\.\. automodule:: (gunz_utils(?:\.[A-Za-z0-9_]+)+)$"
    return set(re.findall(pattern, text, re.MULTILINE))


def test_package_metadata_declares_supported_contracts() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as handle:
        metadata = tomllib.load(handle)
    project = metadata["project"]

    assert project["dependencies"] == []
    assert project["requires-python"] == ">=3.11"
    assert project["license"] == "BSD-3-Clause-Clear"
    assert project["license-files"] == ["LICENSE.md"]
    assert "hatchling>=1.27" in metadata["build-system"]["requires"]

    extras = project["optional-dependencies"]
    assert "pydantic>=2.4.0" in extras["validation"]
    assert "pydantic>=2.4.0" in extras["all"]
    assert "gitpython>=3.1.62" in extras["project"]
    assert "gitpython>=3.1.62" in extras["all"]
    assert "cryptography>=50.0.1" in extras["secure"]
    assert "cryptography>=50.0.1" in extras["all"]

    classifiers = set(project["classifiers"])
    assert "Programming Language :: Python :: 3.11" in classifiers
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Typing :: Typed" in classifiers

    urls = project["urls"]
    for key in ("Source", "Issues", "Changelog", "Security", "Documentation"):
        assert key in urls


def test_pep561_marker_is_present() -> None:
    assert (PACKAGE_DIR / "py.typed").is_file()


def test_api_reference_covers_public_top_level_namespaces() -> None:
    expected = {
        f"gunz_utils.{path.stem}"
        for path in PACKAGE_DIR.glob("*.py")
        if not path.name.startswith("_") and _declares_public_all(path)
    }
    documented = _documented_modules()
    missing = sorted(expected - documented)
    assert missing == []


def test_api_reference_covers_optional_backends_and_benchmark_namespace() -> None:
    expected = {"gunz_utils.benchmark"}
    ext_dir = PACKAGE_DIR / "ext"
    expected.update(
        f"gunz_utils.ext.{path.stem}"
        for path in ext_dir.glob("*.py")
        if not path.name.startswith("_") and _declares_public_all(path)
    )
    documented = _documented_modules()
    missing = sorted(expected - documented)
    assert missing == []


def test_agent_policy_and_documentation_layout() -> None:
    assert (PROJECT_ROOT / "AGENTS.md").is_file()
    assert not (PROJECT_ROOT / "guides").exists()


def test_github_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    refs = re.findall(r"^\s*-?\s*uses:\s+([^\s#]+)", workflow, re.MULTILINE)
    assert refs
    offenders = []
    for ref in refs:
        if ref.startswith("./"):
            continue
        if "@" not in ref:
            offenders.append(ref)
            continue
        _action, revision = ref.rsplit("@", 1)
        if re.fullmatch(r"[0-9a-fA-F]{40}", revision) is None:
            offenders.append(ref)
    assert offenders == []
