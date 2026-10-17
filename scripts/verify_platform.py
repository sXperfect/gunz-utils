#!/usr/bin/env python3
"""Capture real local platform evidence; Linux is preparation only."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SUITES = {
    "filesystem": [
        "tests/test_core/test_audit_directory_publication_regressions.py",
        "tests/test_core/test_audit_atomic_setup_regressions.py",
        "tests/test_core/test_cross_process_content_store.py",
    ],
    "secure-store": [
        "tests/test_secure/test_mode_switch_recovery.py",
        "tests/test_secure/test_cross_process_secure_store.py",
        "tests/test_secure/test_secure_store_process_crash.py",
        "tests/test_secure/test_secure_input_budget_audit.py",
    ],
    "subprocess": [
        "tests/test_core/test_subprocess.py",
        "tests/test_core/test_audit_subprocess_deadline_regressions.py",
        "tests/test_core/test_audit_async_drain_regressions.py",
    ],
}
DARWIN_NODES = [
    "tests/test_core/test_platform_macos_contracts.py::"
    "test_native_darwin_volume_exclusive_directory_rename",
    "tests/test_core/test_platform_macos_contracts.py::"
    "test_native_darwin_private_atomic_write_and_directory_fsync",
    "tests/test_core/test_platform_macos_contracts.py::"
    "test_actual_posix_descriptor_read_refuses_intermediate_symlink",
]
WINDOWS_NODES = [
    "tests/test_core/test_platform_windows_contracts.py::"
    "test_windows_byte_lock_serializes_and_releases_on_holder_exit",
    "tests/test_core/test_platform_windows_contracts.py::"
    "test_windows_directory_rename_preserves_existing_target",
    "tests/test_core/test_platform_windows_contracts.py::"
    "test_windows_store_roundtrip_and_mode_cleanup",
]
FALLBACK_SKIP_REASONS = {
    "Native C extension is not compiled in this environment",
    "Native C extension is required for native differential test",
}


def host_name() -> str:
    """Return actual executing OS without pretending Linux is a native target."""
    return {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(
        platform.system(), "unsupported"
    )


def fingerprint(
    root: Path,
) -> dict[str, Any]:
    """Hash runtime/build/proof inputs, including dirty source and local binaries."""
    files: set[Path] = {root / "pyproject.toml"}
    for folder in ("src", "native", "scripts", "tests"):
        for path in (root / folder).rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix
                in {
                    ".py",
                    ".c",
                    ".h",
                    ".so",
                    ".pyd",
                    ".dll",
                    ".dylib",
                }
            ):
                files.add(path)
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big") + relative)
        digest.update(len(data).to_bytes(8, "big") + data)
    return {"algorithm": "sha256", "value": digest.hexdigest(), "files": len(files)}


def _terminate(
    process: subprocess.Popen[bytes],
) -> dict[str, Any]:
    """Bound cleanup and retain native process-tree strategy evidence."""
    result: dict[str, Any] = {
        "strategy": "process-group" if os.name == "posix" else "tree"
    }
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        taskkill = shutil.which("taskkill")
        result["taskkill_available"] = taskkill is not None
        if taskkill is not None:
            try:
                result["tree_returncode"] = subprocess.run(
                    [taskkill, "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                ).returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                result["tree_error"] = type(exc).__name__
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
        result["reaped"] = True
    except subprocess.TimeoutExpired:
        result["reaped"] = False
    return result


def run_command(
    command: list[str],
    *,
    root: Path,
    artifacts: Path,
    label: str,
    timeout: float,
    env: dict[str, str],
) -> dict[str, Any]:
    """Run argv without a shell, retaining bounded tails and full file-backed logs."""
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if not label or any(
        c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in label
    ):
        raise ValueError("label must be a safe artifact component")
    artifacts.mkdir(parents=True, exist_ok=True)
    stdout_path = artifacts / f"{label}.stdout.log"
    stderr_path = artifacts / f"{label}.stderr.log"
    result: dict[str, Any] = {
        "command": command,
        "timeout": timeout,
        "returncode": None,
    }
    started = time.monotonic()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        try:
            process = subprocess.Popen(
                command,
                cwd=root,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            result.update(status="launch_error", error_type=type(exc).__name__)
        else:
            try:
                result["returncode"] = process.wait(timeout=timeout)
                result["status"] = "passed" if result["returncode"] == 0 else "failed"
            except subprocess.TimeoutExpired:
                result["cleanup"] = _terminate(process)
                result.update(status="timeout", returncode=process.returncode)
            except BaseException:
                _terminate(process)
                raise
    result["duration_seconds"] = round(time.monotonic() - started, 6)
    for name, path in (("stdout", stdout_path), ("stderr", stderr_path)):
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(0, size - 16384))
            result[f"{name}_tail"] = handle.read(16384).decode(
                "utf-8", errors="replace"
            )
        result[f"{name}_bytes"] = size
        result[f"{name}_log"] = str(path)
    return result


def junit_evidence(
    path: Path,
) -> dict[str, Any]:
    """Record each actual skip/failure; malformed or absent reports cannot pass."""
    if not path.is_file():
        return {"valid": False, "error": "missing_junit"}
    if path.stat().st_size > 4 * 1024 * 1024:
        return {"valid": False, "error": "junit_size_limit"}
    try:
        tree = ET.parse(path)  # noqa: GS044
    except (OSError, ET.ParseError) as exc:
        return {"valid": False, "error": type(exc).__name__}
    root = tree.getroot()
    if root.tag not in {"testsuites", "testsuite"}:
        return {"valid": False, "error": "invalid_junit_root"}
    suites = list(root.iter("testsuite"))
    cases = [case for suite in suites for case in suite.findall("testcase")]
    if not suites or len(cases) != len(list(root.iter("testcase"))):
        return {"valid": False, "error": "invalid_junit_structure"}
    summaries: list[dict[str, int]] = []
    for suite in suites:
        summary: dict[str, int] = {}
        for key in ("tests", "errors", "failures", "skipped"):
            raw_count = suite.get(key)
            if raw_count is not None:
                if (
                    len(raw_count) > 20
                    or not raw_count.isascii()
                    or not raw_count.isdecimal()
                ):
                    return {"valid": False, "error": "invalid_junit_count"}
                summary[key] = int(raw_count)
        summaries.append(summary)
    skipped: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    passed = 0
    for case in cases:
        if not case.get("name"):
            return {"valid": False, "error": "missing_testcase_name"}
        if any(
            child.tag
            not in {
                "skipped",
                "failure",
                "error",
                "properties",
                "system-out",
                "system-err",
            }
            for child in case
        ):
            return {"valid": False, "error": "unknown_testcase_disposition"}
        outcomes = False
        for kind in ("skipped", "failure", "error"):
            for outcome in case.findall(kind):
                outcomes = True
                record = {
                    "name": case.get("name", ""),
                    "class": case.get("classname", ""),
                    "kind": kind,
                    "message": outcome.get("message", ""),
                    "type": outcome.get("type", ""),
                }
                (skipped if kind == "skipped" else failed).append(record)
        if not outcomes:
            passed += 1
    return {
        "valid": True,
        "tests": len(cases),
        "passed": passed,
        "suite_summaries": summaries,
        "reported_failures": any(
            summary.get("failures", 0) or summary.get("errors", 0)
            for summary in summaries
        ),
        "skips": skipped,
        "failures": failed,
        "path": str(path),
    }


def attach_test_evidence(
    result: dict[str, Any],
    path: Path,
    *,
    mode: str,
) -> None:
    """Only exact native-only forced-fallback skips are expected coverage exclusions."""
    evidence = junit_evidence(path)
    result["pytest"] = evidence
    result["coverage_gaps"] = []
    result["expected_skips"] = []
    for skip in evidence.get("skips", []):
        expected = (
            mode == "fallback"
            and skip["type"] == "pytest.skip"
            and (
                (
                    skip["class"] == "tests.test_core.test_binary_accel"
                    and skip["message"] in FALLBACK_SKIP_REASONS
                )
                or (
                    skip["class"] == "tests.test_core.test_parser_native_resource_audit"
                    and skip["message"]
                    == "requires asserted compiled native resource audit mode"
                )
            )
        )
        result["expected_skips" if expected else "coverage_gaps"].append(skip)
    result["complete"] = bool(
        result["status"] == "passed"
        and evidence.get("valid")
        and evidence.get("passed", 0)
        and not evidence.get("failures")
        and not evidence.get("reported_failures")
        and not result["coverage_gaps"]
    )
    if mode in {"native", "fallback"}:
        activation = f"verified backend: {mode}"
        result["activation_verified"] = activation in result["stdout_tail"].splitlines()
        result["complete"] = result["complete"] and result["activation_verified"]


def identity_code() -> str:
    """Read actual interpreter/package identity in a fresh process."""
    return """import json, platform, sys, sysconfig
from importlib import metadata
from pathlib import Path
import gunz_utils
packages = {}
for name in ('pytest', 'cryptography', 'ruff', 'mypy'):
    try: packages[name] = metadata.version(name)
    except metadata.PackageNotFoundError: packages[name] = None
print(json.dumps({'system': platform.system(), 'release': platform.release(),
'architecture': platform.machine(), 'version': list(sys.version_info[:3]),
'executable': sys.executable, 'compiler': platform.python_compiler(),
'implementation': platform.python_implementation(),
'include': sysconfig.get_paths()['include'],
'library': sysconfig.get_config_var('LIBRARY'),
'libdir': sysconfig.get_config_var('LIBDIR'),
'ext_suffix': sysconfig.get_config_var('EXT_SUFFIX'),
'configured_cc': sysconfig.get_config_var('CC'), 'packages': packages,
'source_origin': str(Path(gunz_utils.__file__).resolve())}))
"""


def validate_identity(
    identity: dict[str, Any],
    *,
    root: Path,
    system: str,
) -> list[str]:
    """Refuse wrong kernel, old Python, or installed-package source shadowing."""
    errors: list[str] = []
    if identity.get("system") != system:
        errors.append("interpreter OS differs from actual requested host")
    version = identity.get("version")
    if (
        not isinstance(version, list)
        or len(version) != 3
        or any(type(component) is not int or component < 0 for component in version)
    ):
        errors.append(
            "invalid Python version identity; require three nonnegative integers"
        )
    elif tuple(version) < (3, 11):
        errors.append("Python >= 3.11 required")
    source_origin = identity.get("source_origin")
    expected = (root / "src" / "gunz_utils" / "__init__.py").resolve()
    if not isinstance(source_origin, str) or not source_origin:
        errors.append("invalid source import origin identity")
    elif Path(source_origin).resolve() != expected:
        errors.append("source import origin differs from checkout")
    return errors


def verification_environment(
    root: Path,
) -> dict[str, str]:
    """Use checkout/configured checks without inherited pytest selection plugins."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "src")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_PLUGINS", None)
    return env


def missing_versions(
    entries: list[dict[str, Any]],
) -> list[str]:
    """Native acceptance requires actual verified Python 3.11 and 3.12."""
    observed = {
        tuple(entry["identity"]["version"][:2])
        for entry in entries
        if entry.get("identity") and not entry.get("identity_errors")
    }
    return [
        f"{major}.{minor}"
        for major, minor in ((3, 11), (3, 12))
        if (major, minor) not in observed
    ]


def verify(
    *,
    target: str,
    interpreters: list[str],
    output: Path,
    timeout: float = 240,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Prepare locally or verify the actual named native OS, never a shim host."""
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    actual = host_name()
    requested = "linux" if target == "linux-preparation" else target
    report: dict[str, Any] = {
        "schema_version": 1,
        "requested_platform": target,
        "actual_platform": actual,
        "evidence_kind": "preparation"
        if target == "linux-preparation"
        else "native-host",
        "host": {
            "system": platform.system(),
            "kernel": platform.release(),
            "architecture": platform.machine(),
            "python": sys.version,
        },
        "root": str(root.resolve()),
        "interpreters": [],
        "complete": False,
        "native_platform_complete": False,
    }
    if target not in {"windows", "macos", "linux-preparation"} or actual != requested:
        report.update(
            status="refused", reason="requested platform differs from actual host"
        )
    #? Standalone executable must diagnose unsupported launchers explicitly.
    elif sys.version_info < (3, 11):  # noqa: UP036
        report.update(status="refused", reason="launcher requires Python >= 3.11")
    else:
        before = fingerprint(root)
        report["source_fingerprint_before"] = before
        output.parent.mkdir(parents=True, exist_ok=True)
        artifacts = Path(
            tempfile.mkdtemp(prefix="platform-evidence-", dir=output.parent)
        )
        report["artifacts"] = str(artifacts)
        env = verification_environment(root)
        git = shutil.which("git")
        report["revision"] = (
            run_command(
                [git, "rev-parse", "HEAD"],
                root=root,
                artifacts=artifacts,
                label="revision",
                timeout=10,
                env=env,
            )
            if git
            else {
                "status": "missing",
                "reason": "git executable absent; fingerprint used",
            }
        )
        compiler = (
            "cl"
            if actual == "windows"
            else os.environ.get("CC", "clang" if actual == "macos" else "gcc")
        )
        compiler_path = shutil.which(compiler)
        report["native_compiler"] = {"requested": compiler, "path": compiler_path}
        if compiler_path:
            report["native_compiler"]["probe"] = run_command(
                [compiler_path] + ([] if actual == "windows" else ["--version"]),
                root=root,
                artifacts=artifacts,
                label="compiler",
                timeout=10,
                env=env,
            )
        for index, python in enumerate(interpreters):
            prefix = f"python-{index}"
            entry: dict[str, Any] = {"requested_executable": python, "phases": []}
            report["interpreters"].append(entry)
            probe = run_command(
                [python, "-c", identity_code()],
                root=root,
                artifacts=artifacts,
                label=f"{prefix}-identity",
                timeout=30,
                env=env,
            )
            entry["identity_command"] = probe
            try:
                identity = json.loads(probe["stdout_tail"])
                errors = validate_identity(
                    identity, root=root, system=platform.system()
                )
            except (ValueError, TypeError, AttributeError) as exc:
                identity, errors = (
                    {},
                    [f"invalid identity evidence: {type(exc).__name__}"],
                )
            if probe["status"] != "passed":
                errors.append("interpreter identity command failed")
            entry.update(identity=identity, identity_errors=errors)
            if errors:
                entry["complete"] = False
                continue
            suites = {name: list(paths) for name, paths in SUITES.items()}
            if actual == "macos":
                suites["native-platform"] = DARWIN_NODES
            elif actual == "windows":
                suites["native-platform"] = WINDOWS_NODES
            for name, paths in suites.items():
                junit = artifacts / f"{prefix}-{name}.xml"
                phase = run_command(
                    [
                        python,
                        "-m",
                        "pytest",
                        "-q",
                        "--tb=short",
                        f"--junitxml={junit}",
                        *paths,
                    ],
                    root=root,
                    artifacts=artifacts,
                    label=f"{prefix}-{name}",
                    timeout=timeout,
                    env=env,
                )
                phase["name"] = name
                attach_test_evidence(phase, junit, mode="ordinary")
                entry["phases"].append(phase)
            for mode in ("fallback", "native"):
                junit = artifacts / f"{prefix}-{mode}.xml"
                native_env = {
                    **env,
                    "PYTEST_ADDOPTS": shlex.quote(f"--junitxml={junit}"),
                }
                phase = run_command(
                    [
                        python,
                        str(root / "scripts" / "verify_native.py"),
                        "--mode",
                        mode,
                    ],
                    root=root,
                    artifacts=artifacts,
                    label=f"{prefix}-{mode}",
                    timeout=timeout,
                    env=native_env,
                )
                phase["name"] = mode
                attach_test_evidence(phase, junit, mode=mode)
                entry["phases"].append(phase)
            entry["complete"] = all(phase["complete"] for phase in entry["phases"])
        after = fingerprint(root)
        report["source_fingerprint_after"] = after
        report["source_unchanged"] = before == after
        report["missing_python_versions"] = missing_versions(report["interpreters"])
        report["python_matrix_complete"] = not report["missing_python_versions"]
        report["complete"] = bool(
            interpreters
            and report["source_unchanged"]
            and all(entry["complete"] for entry in report["interpreters"])
            and (target == "linux-preparation" or report["python_matrix_complete"])
        )
        report["native_platform_complete"] = report["complete"] and actual in {
            "windows",
            "macos",
        }
        report["status"] = (
            ("prepared" if target == "linux-preparation" else "passed")
            if report["complete"]
            else "incomplete"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    """Write reviewable JSON and return failure for refusals or uncovered checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platform", choices=("windows", "macos", "linux-preparation"), required=True
    )
    parser.add_argument("--python", action="append", dest="interpreters")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "tmp" / "platform-evidence.json"
    )
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args()
    try:
        report = verify(
            target=args.platform,
            interpreters=args.interpreters or [sys.executable],
            output=args.output,
            timeout=args.timeout,
        )
    except (OSError, ValueError) as exc:
        print(f"platform evidence failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"{report['status']}: {args.output}")
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
