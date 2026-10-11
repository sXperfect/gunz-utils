"""Regression checks for truthful local and artifact verification."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.policy


def _load_script(
    name: str,
) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"gunz_ci_regression_{name}", PROJECT_ROOT / "scripts" / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("suffix", ["-other/gunz_utils/__init__.py", "/../other.py"])
def test_origin_guard_rejects_textual_prefix_outside_src(
    suffix: str,
) -> None:
    ci = _load_script("ci")
    assert not ci._origin_ok(str(ci.SRC_DIR) + suffix)


def test_origin_guard_rejects_missing_origin() -> None:
    assert not _load_script("ci")._origin_ok(None)


@pytest.mark.parametrize("skip_style", [False, True])
@pytest.mark.parametrize(
    "ruff_status,mypy_status,style_status",
    [(0, 0, 0), (5, 7, 9), (0, 7, 9), (0, 0, 9)],
)
def test_style_skip_preserves_other_lint_gates_and_failure_precedence(
    monkeypatch: pytest.MonkeyPatch,
    skip_style: bool,
    ruff_status: int,
    mypy_status: int,
    style_status: int,
) -> None:
    ci = _load_script("ci")
    if skip_style:
        monkeypatch.setenv("GUNZ_STYLE_SKIP", "1")
    else:
        monkeypatch.delenv("GUNZ_STYLE_SKIP", raising=False)
    invoked: list[str] = []
    statuses = {
        "ruff": ruff_status,
        "mypy": mypy_status,
        "gunz_style.cli": style_status,
    }

    def run(
        command: list[str],
    ) -> int:
        assert command[1] == "-m"
        invoked.append(command[2])
        return statuses[command[2]]

    monkeypatch.setattr(ci, "_run", run)
    expected = ruff_status or mypy_status or (0 if skip_style else style_status)
    assert ci.run_lint() == expected
    assert invoked == ["ruff", "mypy"] + ([] if skip_style else ["gunz_style.cli"])


def test_import_origin_subprocess_rejects_symlink_outside_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ci = _load_script("ci")
    source = tmp_path / "project" / "src"
    outside = tmp_path / "outside" / "gunz_utils"
    source.mkdir(parents=True)
    outside.mkdir(parents=True)
    (outside / "__init__.py").write_text("", encoding="utf-8")
    (source / "gunz_utils").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(ci, "PROJECT_ROOT", source.parent)
    monkeypatch.setattr(ci, "SRC_DIR", source)

    assert not ci._origin_ok(str(source / "gunz_utils" / "__init__.py"))
    with pytest.raises(SystemExit) as failure:
        ci._verify_import_origin()
    assert failure.value.code == 3


@pytest.mark.parametrize("extra", [None, "validation"])
@pytest.mark.parametrize("installed_ok", [False, True])
def test_isolation_pytest_uses_installed_copy_despite_source_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extra: str | None,
    installed_ok: bool,
) -> None:
    """A good source copy must not conceal a broken installed artifact."""
    ci = _load_script("ci")
    project = tmp_path / "project"
    source = project / "src" / "gunz_utils"
    installed = tmp_path / "site-packages" / "gunz_utils"
    test_dir = "test_ext_stdlib" if extra is None else "test_validation"
    tests = project / "tests" / test_dir
    source.mkdir(parents=True)
    installed.mkdir(parents=True)
    tests.mkdir(parents=True)
    (source / "__init__.py").write_text(
        f"ARTIFACT_OK = {not installed_ok!r}\n", encoding="utf-8"
    )
    (installed / "__init__.py").write_text(
        f"ARTIFACT_OK = {installed_ok!r}\n", encoding="utf-8"
    )
    (project / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["src"]\n', encoding="utf-8"
    )
    (tests / "test_artifact.py").write_text(
        "import gunz_utils\ndef test_artifact():\n"
        "    assert gunz_utils.ARTIFACT_OK\n",
        encoding="utf-8",
    )

    def run_child(
        command,
        *,
        cwd=None,
    ):
        #? Put the fixture's installed copy on the initial interpreter path;
        #? pytest must not override it using the project's pythonpath setting.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(installed.parent)
        env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        env.pop("PYTEST_ADDOPTS", None)
        result = subprocess.run(
            command,
            cwd=project if cwd is None else cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode

    monkeypatch.setattr(ci, "PROJECT_ROOT", project)
    monkeypatch.setattr(
        ci, "_fresh_venv_python", lambda _name: (Path(sys.executable), tmp_path)
    )
    monkeypatch.setattr(ci, "_pip_install", lambda *_args: 0)
    monkeypatch.setattr(ci, "_run_venv", run_child)

    status = ci._case_stdlib() if extra is None else ci._case_extra(extra, test_dir)
    assert status == (0 if installed_ok else 1)


@pytest.mark.parametrize(
    ("sdist_install_status", "missing_sdist_marker", "expected_status"),
    [(0, False, 0), (17, False, 17), (0, True, 1)],
)
def test_sdist_must_install_and_pass_artifact_checks_independently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sdist_install_status: int,
    missing_sdist_marker: bool,
    expected_status: int,
) -> None:
    ci = _load_script("ci")
    dist = tmp_path / "dist"
    installed_artifacts: list[Path] = []
    checked_venvs: list[str] = []

    def fresh(
        name: str,
    ):
        venv = tmp_path / name
        venv.mkdir()
        return venv / "python", venv

    def install(
        python: Path,
        *args: str,
    ) -> int:
        if args == ("build",):
            return 0
        artifact = Path(args[-1])
        installed_artifacts.append(artifact)
        if artifact.suffix == ".gz" and sdist_install_status:
            return sdist_install_status
        package = python.parent / "site-packages" / "gunz_utils"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        if not (artifact.suffix == ".gz" and missing_sdist_marker):
            (package / "py.typed").touch()
        return 0

    def run_child(
        command,
        *,
        cwd=None,
    ):
        if command[1:3] == ["-m", "build"]:
            (dist / "gunz_utils-1.0.0-py3-none-any.whl").touch()
            (dist / "gunz_utils-1.0.0.tar.gz").touch()
            return 0
        venv = Path(command[0]).parent
        checked_venvs.append(venv.name)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(venv / "site-packages")
        return subprocess.run(
            [sys.executable, *command[1:]],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        ).returncode

    monkeypatch.setattr(ci, "DIST_DIR", dist)
    monkeypatch.setattr(ci, "OUTSIDE_CWD", tmp_path / "outside")
    monkeypatch.setattr(ci, "_fresh_venv_python", fresh)
    monkeypatch.setattr(ci, "_pip_install", install)
    monkeypatch.setattr(ci, "_run_venv", run_child)
    monkeypatch.setattr(ci, "_site_packages", lambda venv: venv / "site-packages")

    assert ci._case_wheel_sdist() == expected_status
    assert [item.suffix for item in installed_artifacts] == [".whl", ".gz"]
    assert checked_venvs == (
        ["wheel-install"]
        if sdist_install_status
        else ["wheel-install", "sdist-install"]
    )


def test_compatibility_uses_the_canonical_test_dispatcher(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_ci = _load_script("audit_ci")
    dispatcher = tmp_path / "ci.py"
    dispatcher.write_text(
        "import sys\nraise SystemExit(17 if sys.argv[1:] == ['test'] else 99)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(audit_ci, "CI_SCRIPT", dispatcher)
    assert audit_ci.run_compatibility(sys.executable) == 17


@pytest.mark.parametrize(
    ("path", "packaging", "compatibility"),
    [
        ("src/gunz_utils/__init__.py", True, True),
        ("src/gunz_utils/rate_limit.py", True, True),
        ("src/gunz_utils/py.typed", True, True),
        ("src/gunz_utils/ext/validation_pydantic.py", True, True),
        ("scripts/audit_ci.py", True, True),
        ("scripts/build_native.py", True, True),
        ("tests/test_secure/test_secure_store.py", True, True),
        ("tests/conftest.py", True, True),
        ("pyproject.toml", True, True),
        (".gitignore", True, True),
        (".github/workflows/ci.yml", True, True),
        ("README.md", True, False),
        ("LICENSE.md", True, False),
        ("docs/source/ci.md", False, False),
        ("changes/example.fixed.md", False, False),
        ("CONTRIBUTING.md", False, False),
        ("benchmarks/workloads.py", False, True),
        ("docs/source/ci.md\nsrc/gunz_utils/__init__.py", True, True),
    ],
)
def test_pr_gate_selection_covers_artifact_and_isolation_inputs(
    path: str,
    packaging: bool,
    compatibility: bool,
) -> None:
    """Execute the workflow's actual classifier, including the docs fast path."""
    text = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    start = text.index("            packaging_changed=false")
    end_marker = '            done <<< "$changed_files"'
    end = text.index(end_marker, start) + len(end_marker)
    classifier = textwrap.dedent(text[start:end])
    env = dict(os.environ)
    env["changed_files"] = path
    result = subprocess.run(
        [
            "bash", "-e", "-c", classifier
            + '\nprintf "%s %s" "$packaging_changed" "$non_docs_changed"',
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert result.stdout == f"{str(packaging).lower()} {str(compatibility).lower()}"
