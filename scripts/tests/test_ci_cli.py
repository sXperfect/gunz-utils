"""Narrow subprocess/argument tests for the local CI dispatcher.

These intentionally do NOT run the full 712-test suite. They exercise command
dispatch, unknown-command handling, exit-status propagation, release metadata,
guard, and the packaging isolation-matrix loop (with the heavy venv case
functions stubbed, so no network and no fresh venvs are created).

Run from the project root with the hyperion env:
    python -m pytest scripts/tests/test_ci_cli.py -q
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CI_PY = PROJECT_ROOT / "scripts" / "ci.py"


def _load_ci():
    spec = importlib.util.spec_from_file_location("gunz_ci", CI_PY)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CI_PY), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_cli_help_lists_all_gates() -> None:
    result = _run_cli("--help")
    assert result.returncode == 0
    for gate in ("release", "lint", "test", "docs", "packaging", "all"):
        assert gate in result.stdout


def test_cli_unknown_command_is_nonzero() -> None:
    result = _run_cli("bogus-gate")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr or "unknown" in result.stderr.lower()


def test_cli_no_command_is_nonzero() -> None:
    result = _run_cli()
    assert result.returncode == 2


def test_packaging_gate_runs_all_cases_without_network(monkeypatch) -> None:
    # The packaging gate is a fresh-venv isolation matrix (zero-dep, stdlib,
    # per-extra validation/project/observability/secure, plot, wheel/sdist).
    # Running it for real would create 8 venvs and hit the network, so this unit
    # test stubs every heavy case function to a no-op success and asserts the
    # runner invokes the full matrix and returns 0. Real proof of each case is
    # `python scripts/ci.py packaging` (exit 0, 8/8), not this unit test.
    ci = _load_ci()
    invoked: dict[str, int] = {}

    def make_fake(key: str):
        def fake(*_args, **_kwargs):
            invoked[key] = invoked.get(key, 0) + 1
            return 0

        return fake

    # The four per-extra cases all route through _case_extra.
    monkeypatch.setattr(ci, "_case_zero_dep", make_fake("zero-dep"))
    monkeypatch.setattr(ci, "_case_stdlib", make_fake("stdlib"))
    monkeypatch.setattr(ci, "_case_extra", make_fake("extra"))
    monkeypatch.setattr(ci, "_case_plot", make_fake("plot"))
    monkeypatch.setattr(ci, "_case_wheel_sdist", make_fake("wheel/sdist"))

    assert ci.run_packaging() == 0
    assert invoked == {
        "zero-dep": 1,
        "stdlib": 1,
        "extra": 4,
        "plot": 1,
        "wheel/sdist": 1,
    }


def test_origin_guard_accepts_worktree_path() -> None:
    ci = _load_ci()
    inside = str(PROJECT_ROOT / "src" / "gunz_utils" / "__init__.py")
    assert ci._origin_ok(inside)


def test_origin_guard_rejects_outside_path() -> None:
    ci = _load_ci()
    outside = (
        "/home/sxperfect/projects/hyperion/libs/gunz-utils/"
        "src/gunz_utils/__init__.py"
    )
    assert not ci._origin_ok(outside)


def test_run_propagates_failure_exit_code() -> None:
    ci = _load_ci()
    failing = [sys.executable, "-c", "import sys; sys.exit(9)"]
    assert ci._run(failing) == 9


def test_run_passes_clean_command() -> None:
    ci = _load_ci()
    passing = [sys.executable, "-c", "pass"]
    assert ci._run(passing) == 0


def test_all_stops_on_first_failure(monkeypatch) -> None:
    ci = _load_ci()
    calls: list[str] = []

    def fake_release() -> int:
        calls.append("release")
        return 1

    def fake_lint() -> int:
        calls.append("lint")
        return 0

    monkeypatch.setattr(ci, "run_release", fake_release)
    monkeypatch.setattr(ci, "run_lint", fake_lint)
    assert ci.run_all() == 1
    assert calls == ["release"]
