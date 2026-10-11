"""Actual-host guards and evidence conservation for the portable verifier."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest


@pytest.fixture
def verifier() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts" / "verify_platform.py"
    spec = importlib.util.spec_from_file_location("platform_verifier_for_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("verifier module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_requested_os_mismatch_never_runs_a_command(
    verifier: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual = verifier.host_name()
    requested = "macos" if actual != "macos" else "windows"

    def forbidden(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise AssertionError("wrong-platform request launched a process")

    monkeypatch.setattr(verifier, "run_command", forbidden)
    output = tmp_path / "refused.json"
    report = verifier.verify(
        target=requested, interpreters=[sys.executable], output=output
    )
    assert report["status"] == "refused"
    assert report["actual_platform"] == actual
    assert not report["complete"]
    assert not report["native_platform_complete"]
    assert json.loads(output.read_text())["status"] == "refused"


def test_identity_refuses_old_python_wrong_kernel_and_source_shadowing(
    verifier: Any,
    tmp_path: Path,
) -> None:
    origin = tmp_path / "src" / "gunz_utils" / "__init__.py"
    identity = {
        "system": "Windows",
        "version": [3, 11, 14],
        "source_origin": str(origin),
    }
    assert verifier.validate_identity(identity, root=tmp_path, system="Windows") == []
    identity.update(
        system="Linux", version=[3, 10, 9], source_origin=str(tmp_path / "other.py")
    )
    errors = verifier.validate_identity(identity, root=tmp_path, system="Windows")
    assert len(errors) == 3
    assert any("source import" in error for error in errors)


def test_source_fingerprint_changes_for_dirty_code_and_proof_inputs(
    verifier: Any,
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text("version = 'synthetic'")
    source = tmp_path / "src"
    source.mkdir()
    module = source / "module.py"
    module.write_text("value = 1\n")
    original = verifier.fingerprint(tmp_path)
    module.write_text("value = 2\n")
    changed = verifier.fingerprint(tmp_path)
    assert changed["value"] != original["value"]
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_oracle.py").write_text("synthetic proof input\n")
    assert verifier.fingerprint(tmp_path)["files"] == changed["files"] + 1


def test_native_version_matrix_does_not_accept_single_or_invalid_interpreter(
    verifier: Any,
) -> None:
    entries = [{"identity": {"version": [3, 11, 14]}, "identity_errors": []}]
    assert verifier.missing_versions(entries) == ["3.12"]
    entries.append(
        {"identity": {"version": [3, 12, 12]}, "identity_errors": ["bad origin"]}
    )
    assert verifier.missing_versions(entries) == ["3.12"]
    entries[-1]["identity_errors"] = []
    assert verifier.missing_versions(entries) == []


def test_junit_preserves_unexplained_skip_and_failure_details(
    verifier: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "results.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="success"/>'
        '<testcase name="native"><skipped message="missing compiler"/></testcase>'
        '<testcase name="broken"><failure message="bad bytes"/></testcase>'
        "</testsuite></testsuites>"
    )
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: native",
    }
    verifier.attach_test_evidence(result, path, mode="native")
    assert result["pytest"]["tests"] == 3
    assert result["pytest"]["passed"] == 1
    assert result["pytest"]["failures"][0]["message"] == "bad bytes"
    assert result["coverage_gaps"][0]["name"] == "native"
    assert not result["complete"]


def test_only_exact_forced_fallback_skips_are_expected(
    verifier: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "fallback.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="reference"/>'
        '<testcase classname="tests.test_core.test_binary_accel" name="differential">'
        '<skipped type="pytest.skip" message="Native C extension is required '
        'for native differential test"/>'
        "</testcase></testsuite></testsuites>"
    )
    fallback = {"status": "passed", "stdout_tail": "verified backend: fallback"}
    verifier.attach_test_evidence(fallback, path, mode="fallback")
    assert fallback["complete"]
    assert len(fallback["expected_skips"]) == 1
    native = {"status": "passed", "stdout_tail": "verified backend: native"}
    verifier.attach_test_evidence(native, path, mode="native")
    assert not native["complete"]
    assert len(native["coverage_gaps"]) == 1


@pytest.mark.parametrize(
    "mode,kind,module,complete",
    [
        ("fallback", "pytest.skip", "test_parser_native_resource_audit", True),
        ("native", "pytest.skip", "test_parser_native_resource_audit", False),
        ("fallback", "pytest.xfail", "test_parser_native_resource_audit", False),
        ("fallback", "pytest.skip", "unrelated_audit", False),
    ],
)
def test_parser_native_exclusion_requires_exact_fallback_skip(
    verifier: Any,
    tmp_path: Path,
    mode: str,
    kind: str,
    module: str,
    complete: bool,
) -> None:
    path = tmp_path / "parser-native.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="reference"/>'
        f'<testcase classname="tests.test_core.{module}" name="native-lifetime">'
        f'<skipped type="{kind}" '
        'message="requires asserted compiled native resource audit mode"/>'
        '</testcase></testsuite></testsuites>'
    )
    result = {"status": "passed", "stdout_tail": f"verified backend: {mode}"}
    verifier.attach_test_evidence(result, path, mode=mode)
    assert result["complete"] is complete
    assert len(result["expected_skips"]) == int(complete)
    assert len(result["coverage_gaps"]) == int(not complete)


def test_missing_or_empty_junit_cannot_certify_activation(
    verifier: Any,
    tmp_path: Path,
) -> None:
    missing = {"status": "passed", "stdout_tail": "verified backend: native"}
    path = tmp_path / "absent.xml"
    verifier.attach_test_evidence(missing, path, mode="native")
    assert not missing["complete"]
    path.write_text("<testsuites/>")
    verifier.attach_test_evidence(missing, path, mode="native")
    assert not missing["complete"]


def test_real_runner_timeout_reaps_process_and_reports_logs(
    verifier: Any,
    tmp_path: Path,
) -> None:
    result = verifier.run_command(
        [
            sys.executable,
            "-c",
            "import time;print('started',flush=True);time.sleep(10)",
        ],
        root=tmp_path,
        artifacts=tmp_path / "evidence",
        label="timeout",
        timeout=0.1,
        env=dict(os.environ),
    )
    assert result["status"] == "timeout"
    assert result["cleanup"]["reaped"]
    assert result["returncode"] != 0
    assert Path(result["stdout_log"]).is_file()
    assert result["duration_seconds"] < 6


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -1, 0, True])
def test_invalid_timeout_precedes_process_or_artifact_creation(
    verifier: Any,
    tmp_path: Path,
    timeout: float,
) -> None:
    artifacts = tmp_path / "not-created"
    with pytest.raises(ValueError, match="finite and positive"):
        verifier.run_command(
            [sys.executable],
            root=tmp_path,
            artifacts=artifacts,
            label="invalid",
            timeout=timeout,
            env=dict(os.environ),
        )
    assert not artifacts.exists()


def test_real_launch_failure_is_not_a_passing_empty_run(
    verifier: Any,
    tmp_path: Path,
) -> None:
    result = verifier.run_command(
        [str(tmp_path / "nonexistent-interpreter")],
        root=tmp_path,
        artifacts=tmp_path / "logs",
        label="missing",
        timeout=1,
        env=dict(os.environ),
    )
    assert result["status"] == "launch_error"
    assert result["error_type"] == "FileNotFoundError"
    assert result["returncode"] is None


@pytest.mark.parametrize(
    "xml",
    [
        '<unrelated><testcase name="invented"/></unrelated>',
        '<testsuites><testcase name="misplaced"/></testsuites>',
        "<testsuites><testsuite><testcase/></testsuite></testsuites>",
        '<testsuites><testsuite tests="-1"><testcase name="a"/>'
        "</testsuite></testsuites>",
        '<testsuites><testsuite><testcase name="a"><xfail/></testcase>'
        "</testsuite></testsuites>",
    ],
)
def test_malformed_junit_structure_cannot_pass_native_phase(
    verifier: Any,
    tmp_path: Path,
    xml: str,
) -> None:
    path = tmp_path / "malformed.xml"
    path.write_text(xml)
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: native",
    }
    verifier.attach_test_evidence(result, path, mode="native")
    assert not result["pytest"]["valid"]
    assert not result["complete"]


@pytest.mark.parametrize(
    "skip_type,case_class",
    [
        ("pytest.xfail", "tests.test_core.test_binary_accel"),
        ("pytest.skip", "tests.test_core.shadow_test_binary_accel"),
        ("", "tests.test_core.test_binary_accel"),
    ],
)
def test_expected_reason_does_not_hide_xfail_or_unrelated_skip(
    verifier: Any,
    tmp_path: Path,
    skip_type: str,
    case_class: str,
) -> None:
    path = tmp_path / "skip.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="reference"/>'
        f'<testcase classname="{case_class}" name="differential">'
        f'<skipped type="{skip_type}" '
        'message="Native C extension is required for native differential test"/>'
        "</testcase></testsuite></testsuites>"
    )
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: fallback",
    }
    verifier.attach_test_evidence(result, path, mode="fallback")
    assert not result["complete"]
    assert result["expected_skips"] == []
    assert result["coverage_gaps"][0]["type"] == skip_type


def test_fallback_all_skipped_has_no_executed_proof(
    verifier: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "only-skips.xml"
    path.write_text(
        "<testsuites><testsuite><testcase "
        'classname="tests.test_core.test_binary_accel" '
        'name="differential"><skipped type="pytest.skip" '
        'message="Native C extension is required for native differential test"/>'
        "</testcase></testsuite></testsuites>"
    )
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: fallback",
    }
    verifier.attach_test_evidence(result, path, mode="fallback")
    assert result["pytest"]["passed"] == 0
    assert len(result["expected_skips"]) == 1
    assert not result["complete"]


def test_failed_summary_and_multiple_outcomes_do_not_manufacture_passes(
    verifier: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "outcomes.xml"
    path.write_text(
        '<testsuites><testsuite failures="1"><testcase name="appears_passed"/>'
        '<testcase name="broken"><failure message="call failed"/>'
        '<error message="cleanup failed"/></testcase></testsuite></testsuites>'
    )
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: native",
    }
    verifier.attach_test_evidence(result, path, mode="native")
    assert result["pytest"]["passed"] == 1
    assert result["pytest"]["reported_failures"]
    assert len(result["pytest"]["failures"]) == 2
    assert not result["complete"]
    path.write_text(
        '<testsuites><testsuite failures="1"><testcase name="a"/>'
        "</testsuite></testsuites>"
    )
    verifier.attach_test_evidence(result, path, mode="native")
    assert not result["complete"]


@pytest.mark.parametrize(
    "version", [[3, 11], [3, 11, -1], [3, 11, True], [3, 11, []], "3.11.14", None]
)
def test_malformed_identity_version_is_refused_without_type_errors(
    verifier: Any,
    tmp_path: Path,
    version: Any,
) -> None:
    identity = {
        "system": "Linux",
        "version": version,
        "source_origin": str(tmp_path / "src/gunz_utils/__init__.py"),
    }
    errors = verifier.validate_identity(identity, root=tmp_path, system="Linux")
    assert any("invalid Python version" in error for error in errors)


def test_malformed_source_origin_is_an_explicit_identity_error(
    verifier: Any,
    tmp_path: Path,
) -> None:
    identity = {"system": "Linux", "version": [3, 11, 14], "source_origin": None}
    assert any(
        "invalid source" in error
        for error in verifier.validate_identity(identity, root=tmp_path, system="Linux")
    )


def test_inherited_selection_plugin_cannot_suppress_a_failing_oracle(
    verifier: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "selection_plugin.py").write_text(
        "def pytest_collection_modifyitems(items):\n"
        '    items[:] = [item for item in items if item.name != "test_bad"]\n'
    )
    tests = tmp_path / "test_oracles.py"
    tests.write_text(
        "def test_good():\n    assert True\ndef test_bad():\n    assert False\n"
    )
    monkeypatch.setenv("PYTEST_PLUGINS", "selection_plugin")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_good")
    env = verifier.verification_environment(tmp_path)
    assert "PYTEST_PLUGINS" not in env
    assert "PYTEST_ADDOPTS" not in env
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tests)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert "1 failed, 1 passed" in result.stdout


def test_actual_pytest_xfail_remains_a_coverage_gap(
    verifier: Any,
    tmp_path: Path,
) -> None:
    tests = tmp_path / "test_binary_accel.py"
    tests.write_text(
        "import pytest\n"
        '@pytest.mark.xfail(reason="Native C extension is required for native '
        'differential test")\n'
        "def test_oracle():\n    assert False\n"
    )
    junit = tmp_path / "actual.xml"
    env = verifier.verification_environment(tmp_path)
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tests), f"--junitxml={junit}"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert run.returncode == 0
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: fallback",
    }
    verifier.attach_test_evidence(result, junit, mode="fallback")
    assert result["pytest"]["skips"][0]["type"] == "pytest.xfail"
    assert result["pytest"]["passed"] == 0
    assert not result["complete"]


@pytest.mark.parametrize(
    "text",
    [
        "not verified backend: native",
        "verified backend: native_absent",
        "diagnostic: verified backend: native",
    ],
)
def test_activation_requires_the_exact_helper_receipt_line(
    verifier: Any,
    tmp_path: Path,
    text: str,
) -> None:
    path = tmp_path / "passed.xml"
    path.write_text(
        '<testsuites><testsuite><testcase name="proof"/></testsuite></testsuites>'
    )
    result: dict[str, Any] = {"status": "passed", "stdout_tail": text}
    verifier.attach_test_evidence(result, path, mode="native")
    assert not result["activation_verified"]
    assert not result["complete"]


def test_oversized_junit_counter_is_structured_invalid_evidence(
    verifier: Any,
    tmp_path: Path,
) -> None:
    path = tmp_path / "large-counter.xml"
    path.write_text(
        '<testsuites><testsuite tests="'
        + "9" * 5000
        + '"><testcase name="proof"/></testsuite></testsuites>'
    )
    result: dict[str, Any] = {
        "status": "passed",
        "stdout_tail": "verified backend: native",
    }
    verifier.attach_test_evidence(result, path, mode="native")
    assert result["pytest"]["error"] == "invalid_junit_count"
    assert not result["complete"]
