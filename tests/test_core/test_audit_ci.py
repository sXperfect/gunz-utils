"""Tests for the aggregate audit CI orchestrator."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

try:
    import pytest

    pytestmark = pytest.mark.policy
except ImportError:
    pytest = None  # type: ignore[assignment]



def _load_audit_ci() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "audit_ci.py"
    spec = importlib.util.spec_from_file_location("gunz_audit_ci", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit_ci = _load_audit_ci()


def _load_legacy_ci() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "ci.py"
    spec = importlib.util.spec_from_file_location("gunz_legacy_ci", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


legacy_ci = _load_legacy_ci()


def test_collect_results_keeps_running_after_independent_failures() -> None:
    calls: list[str] = []
    statuses = {
        "release": 2,
        "lint": 1,
        "test": 0,
        "docs": 3,
        "packaging": 0,
    }

    def runner(name: str) -> int:
        calls.append(name)
        return statuses[name]

    compatibility: list[str] = []

    def compat(python: str) -> int:
        compatibility.append(python)
        return 4

    results = audit_ci.collect_results(
        gate_runner=runner,
        compatibility_python="python3.12",
        compatibility_runner=compat,
    )

    assert calls == list(audit_ci.DEFAULT_GATES)
    assert compatibility == ["python3.12"]
    assert [(item.name, item.returncode) for item in results] == [
        ("release", 2),
        ("lint", 1),
        ("test", 0),
        ("docs", 3),
        ("packaging", 0),
        ("python-compatibility", 4),
    ]


def test_collect_results_can_fail_fast_for_local_diagnosis() -> None:
    calls: list[str] = []

    def runner(name: str) -> int:
        calls.append(name)
        return 1 if name == "lint" else 0

    results = audit_ci.collect_results(
        gate_runner=runner,
        fail_fast=True,
    )

    assert calls == ["release", "lint"]
    assert [(item.name, item.returncode) for item in results] == [
        ("release", 0),
        ("lint", 1),
    ]


def test_gate_exception_becomes_visible_failure_and_collection_continues() -> None:
    calls: list[str] = []

    def runner(name: str) -> int:
        calls.append(name)
        if name == "release":
            raise RuntimeError("boom")
        return 0

    results = audit_ci.collect_results(gate_runner=runner)

    assert calls == list(audit_ci.DEFAULT_GATES)
    assert results[0].name == "release"
    assert results[0].returncode == 70
    assert all(item.returncode == 0 for item in results[1:])


def test_json_summary_is_complete_and_machine_readable(tmp_path: Path) -> None:
    results = [
        audit_ci.GateResult("release", 0),
        audit_ci.GateResult("lint", 1),
        audit_ci.GateResult("test", 0),
    ]
    target = tmp_path / "nested" / "summary.json"

    audit_ci.write_json_summary(target, results)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {
        "passed": False,
        "results": [
            {"name": "release", "returncode": 0},
            {"name": "lint", "returncode": 1},
            {"name": "test", "returncode": 0},
        ],
        "schema_version": 1,
    }


def test_packaging_gate_collects_all_case_failures(monkeypatch) -> None:
    calls: list[str] = []

    def case(name: str, status: int = 0):
        def run() -> int:
            calls.append(name)
            return status

        return run

    def extra(name: str, _test_dir: str) -> int:
        calls.append(name)
        return 0

    monkeypatch.setattr(legacy_ci, "_case_zero_dep", case("zero-dep", 2))
    monkeypatch.setattr(legacy_ci, "_case_stdlib", case("stdlib"))
    monkeypatch.setattr(legacy_ci, "_case_extra", extra)
    monkeypatch.setattr(legacy_ci, "_case_plot", case("plot", 3))
    monkeypatch.setattr(legacy_ci, "_case_wheel_sdist", case("wheel/sdist"))

    assert legacy_ci.run_packaging() == 1
    assert calls == [
        "zero-dep",
        "stdlib",
        "validation",
        "project",
        "observability",
        "secure",
        "plot",
        "wheel/sdist",
    ]


def test_gate_exception_output_redacts_exception_message(capsys) -> None:
    secret = "tooling-secret-value"

    def runner(_name: str) -> int:
        raise RuntimeError(secret)

    results = audit_ci.collect_results(
        gates=("lint",),
        gate_runner=runner,
    )

    captured = capsys.readouterr()
    assert results == [audit_ci.GateResult("lint", 70)]
    assert "RuntimeError" in captured.err
    assert secret not in captured.err


def test_audit_ci_skips_packaging_when_requested(monkeypatch) -> None:
    captured_gates: list[str] = []

    def fake_collect(gates, **_kwargs):
        captured_gates.extend(gates)
        return []

    monkeypatch.setattr(audit_ci, "collect_results", fake_collect)
    monkeypatch.setattr(audit_ci, "print_summary", lambda _res: None)
    monkeypatch.setattr(audit_ci, "write_github_summary", lambda _res: None)

    exit_code = audit_ci.main(["--skip-release", "--skip-packaging"])
    assert exit_code == 0
    assert "release" not in captured_gates
    assert "packaging" not in captured_gates
    assert captured_gates == ["lint", "test", "docs"]


def test_audit_ci_skips_compat_when_requested(monkeypatch) -> None:
    captured_kwargs: dict = {}

    def fake_collect(gates, **kwargs):
        captured_kwargs.update(kwargs)
        return []

    monkeypatch.setattr(audit_ci, "collect_results", fake_collect)
    monkeypatch.setattr(audit_ci, "print_summary", lambda _res: None)
    monkeypatch.setattr(audit_ci, "write_github_summary", lambda _res: None)

    exit_code = audit_ci.main(["--compat-python", "python3.12", "--skip-compat"])
    assert exit_code == 0
    assert captured_kwargs.get("compatibility_python") is None

