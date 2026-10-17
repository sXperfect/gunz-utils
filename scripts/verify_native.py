#!/usr/bin/env python3
"""Require real native activation and fallback in isolated source copies."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = (
    "tests/test_core/test_binary_accel.py",
    "tests/test_core/test_serialization.py",
    "tests/test_core/test_audit_native_safety_regressions.py",
    "tests/test_core/test_parser_native_resource_audit.py",
    "tests/test_core/test_stats.py",
    "tests/test_core/test_v1_17_capabilities.py",
    "tests/test_core/test_v1_17_1_audit_regressions.py",
)


def activation_code(
    source: Path,
    *,
    native: bool,
) -> str:
    """Return an independent import/dispatch check run before the proof suite."""
    return (
        "from pathlib import Path\n"
        "from gunz_utils import binary, serialization, stats\n"
        f"source = Path({str(source)!r}).resolve()\n"
        "if not Path(binary.__file__).resolve().is_relative_to(source):\n"
        "    raise SystemExit('native verification imported outside isolated source')\n"
        "hooks = (binary._accel_encode, binary._accel_decode, "
        "serialization._accel_is_json_clean, stats._accel_fast_summary, "
        "stats._accel_update_running_stats)\n"
        f"native = {native!r}\n"
        "if native and not all(hook is not None for hook in hooks):\n"
        "    raise SystemExit('native activation required; fallback is not proof')\n"
        "if not native and any(hook is not None for hook in hooks):\n"
        "    raise SystemExit('forced fallback unexpectedly loaded native code')\n"
        "print('verified backend:', 'native' if native else 'fallback')\n"
    )


def verify(
    *,
    mode: str = "all",
) -> int:
    """Build/test outside src; compiler failures remain visible gate failures."""
    scratch = ROOT / "tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="native-verify-", dir=scratch) as directory:
        source = Path(directory) / "src"
        package = source / "gunz_utils"
        shutil.copytree(
            ROOT / "src" / "gunz_utils",
            package,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.so", "*.pyd", "*.dll", "*.dylib"
            ),
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = str(source)
        for native in (False, True):
            if mode == "native" and not native or mode == "fallback" and native:
                continue
            if native:
                command = [
                    sys.executable,
                    str(ROOT / "scripts" / "build_native.py"),
                    "--output-dir",
                    str(package),
                ]
                result = subprocess.run(command, cwd=ROOT, env=env, timeout=120)
                if result.returncode:
                    return result.returncode
            result = subprocess.run(
                [sys.executable, "-c", activation_code(source, native=native)],
                cwd=ROOT,
                env=env,
                timeout=30,
            )
            if result.returncode:
                return result.returncode
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-o", f"pythonpath={source}", *TESTS],
                cwd=ROOT,
                env=env,
                timeout=180,
            )
            if result.returncode:
                return result.returncode
    return 0


def main() -> int:
    """Run requested mode with explicit failures and temporary cleanup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("all", "native", "fallback"), default="all")
    args = parser.parse_args()
    try:
        return verify(mode=args.mode)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"native verification failed: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
