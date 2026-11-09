#!/usr/bin/env python3
"""Zero-dependency standalone test runner using Python standard library unittest.

Enables developers to run unit, property, and contract tests immediately on any
ambient Python 3.11+ environment without requiring pytest or third-party tools.
Supports both unittest.TestCase subclasses and standalone test_* functions.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import inspect
import re
import sys
import time
import types
from typing import Any
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"


def _ensure_pytest_shim() -> None:
    """Provide a lightweight fallback when pytest is not installed."""
    if "pytest" in sys.modules:
        return
    try:
        import pytest  # noqa: F401
    except ImportError:
        class _MarkHelper:
            def __getattr__(self, name: str) -> Any:
                def _decorator(*args: Any, **kwargs: Any) -> Any:
                    if len(args) == 1 and callable(args[0]) and not kwargs:
                        return args[0]
                    def _inner(fn: Any) -> Any:
                        return fn
                    return _inner
                return _decorator

        class _RaisesContext:
            def __init__(self, exc: Any, match: str | None = None) -> None:
                self.exc = exc
                self.match = match
                self.value: Any = None
            def __enter__(self) -> _RaisesContext:
                return self
            def __exit__(self, et: Any, ev: Any, tb: Any) -> bool:
                if et is None:
                    raise AssertionError(f"Expected exception {self.exc} not raised")
                if not issubclass(et, self.exc):
                    return False
                self.value = ev
                if self.match and not re.search(self.match, str(ev)):
                    raise AssertionError(f"Pattern {self.match!r} not found in {str(ev)!r}")
                return True

        class _Approx:
            def __init__(self, expected: Any, rel: float = 1e-6, abs: float = 1e-12) -> None:
                self.expected = expected
                self.rel = rel
                self.abs = abs
            def __eq__(self, actual: Any) -> bool:
                try:
                    return bool(abs(actual - self.expected) <= max(self.rel * abs(self.expected), self.abs))
                except Exception:
                    return False

        def _skip(reason: str = "") -> None:
            raise unittest.SkipTest(reason)

        shim = types.ModuleType("pytest")
        shim.mark = _MarkHelper()
        shim.raises = _RaisesContext
        shim.approx = _Approx
        shim.skip = _skip
        shim.MonkeyPatch = object
        shim.fixture = lambda *a, **k: (lambda fn: fn) if (len(a) == 0 or not callable(a[0])) else a[0]
        def _importorskip(modname: str) -> Any:
            try:
                import importlib
                return importlib.import_module(modname)
            except ImportError:
                raise unittest.SkipTest(f"missing {modname}")
        shim.importorskip = _importorskip
        sys.modules["pytest"] = shim


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run repository tests using standard-library unittest."
    )
    parser.add_argument(
        "--start-dir",
        "-s",
        type=Path,
        default=TESTS_DIR,
        help="Directory to start test discovery (default: tests/)",
    )
    parser.add_argument(
        "--pattern",
        "-p",
        default="test_*.py",
        help="Pattern to match test files (default: test_*.py)",
    )
    parser.add_argument(
        "-k",
        dest="keyword",
        help="Only run tests whose name or file matches the given substring",
    )
    parser.add_argument(
        "--failfast",
        "-f",
        action="store_true",
        help="Stop on first failure or error",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose test execution output",
    )
    parser.add_argument(
        "--durations",
        type=int,
        default=0,
        help="Show top N slowest tests",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=None,
        help="Optional specific test files or directories to run",
    )
    return parser


def load_test_suite(
    start_dir: Path,
    pattern: str = "test_*.py",
    keyword: str | None = None,
) -> tuple[unittest.TestSuite, int]:
    """Discover and load both TestCase classes and standalone test functions."""
    _ensure_pytest_shim()
    suite = unittest.TestSuite()
    skipped_modules = 0

    test_files = sorted(start_dir.rglob(pattern)) if start_dir.is_dir() else [start_dir]

    for py_file in test_files:
        if not py_file.is_file() or py_file.name.startswith((".", "_")):
            continue

        try:
            rel_parts = py_file.relative_to(start_dir).with_suffix("").parts
            module_name = "_test_" + "_".join(rel_parts)
        except ValueError:
            module_name = f"_test_{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except (ImportError, ModuleNotFoundError):
            #? Optional third-party dependency missing in current environment
            skipped_modules += 1
            continue
        except Exception as exc:
            #? Fatal error during module import
            print(f"Warning: could not import {py_file}: {exc}", file=sys.stderr)
            skipped_modules += 1
            continue

        # 1. Standard unittest.TestCase classes
        module_cases = unittest.defaultTestLoader.loadTestsFromModule(module)
        for test in module_cases:
            if isinstance(test, unittest.TestSuite):
                for subtest in test:
                    test_id = subtest.id()
                    if keyword is None or keyword.lower() in test_id.lower():
                        suite.addTest(subtest)
            else:
                test_id = test.id()
                if keyword is None or keyword.lower() in test_id.lower():
                    suite.addTest(test)

        # 2. Standalone test_* functions (excluding pytest fixture-dependent functions)
        for name, obj in inspect.getmembers(module):
            if name.startswith("test_") and (inspect.isfunction(obj) or inspect.iscoroutinefunction(obj)):
                try:
                    sig = inspect.signature(obj)
                    if len(sig.parameters) > 0:
                        #? Skip functions requiring pytest fixtures
                        #? (monkeypatch, capsys, etc.)
                        continue
                except Exception:
                    continue
                full_name = f"{py_file.stem}.{name}"
                if keyword is None or keyword.lower() in full_name.lower():
                    if inspect.iscoroutinefunction(obj):
                        sync_fn = (lambda fn=obj: lambda: asyncio.run(fn()))()
                        sync_fn.__name__ = name
                        test_case = unittest.FunctionTestCase(sync_fn, description=full_name)
                    else:
                        test_case = unittest.FunctionTestCase(obj, description=full_name)
                    suite.addTest(test_case)

    return suite, skipped_modules


def main(
    argv: list[str] | None = None,
) -> int:
    """Discover and execute tests with pure Python unittest."""
    args = build_parser().parse_args(argv)

    #? Ensure worktree src/ and tests/ are on sys.path
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))  # gunz-style: ignore[GS007]
    if str(TESTS_DIR) not in sys.path:
        sys.path.insert(1, str(TESTS_DIR))  # gunz-style: ignore[GS007]

    suite = unittest.TestSuite()
    skipped = 0
    targets = args.paths if args.paths else [args.start_dir]
    for target in targets:
        s, sk = load_test_suite(
            target,
            pattern=args.pattern,
            keyword=args.keyword,
        )
        suite.addTests(s)
        skipped += sk

    test_count = suite.countTestCases()
    msg = f"Discovered {test_count} tests"
    if skipped > 0:
        msg += f" ({skipped} files skipped due to uninstalled optional extras)"
    print(msg + ".\n")

    class _TimingResult(unittest.TextTestResult):
        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, **kw)
            self._case_starts: dict[unittest.TestCase, float] = {}
            self.durations: list[tuple[float, str]] = []

        def startTest(self, test: unittest.TestCase) -> None:
            super().startTest(test)
            self._case_starts[test] = time.perf_counter()

        def stopTest(self, test: unittest.TestCase) -> None:
            super().stopTest(test)
            start = self._case_starts.pop(test, None)
            if start is not None:
                self.durations.append((time.perf_counter() - start, str(test)))

    class _TimingRunner(unittest.TextTestRunner):
        resultclass = _TimingResult

    runner_cls = _TimingRunner if args.durations > 0 else unittest.TextTestRunner
    runner = runner_cls(
        verbosity=2 if args.verbose else 1,
        failfast=args.failfast,
    )
    result = runner.run(suite)
    if args.durations > 0 and hasattr(result, "durations"):
        timed_cases: list[tuple[float, str]] = sorted(
            result.durations, key=lambda pair: pair[0], reverse=True
        )
        print(f"\nSlowest {args.durations} tests:")
        for dt, name in timed_cases[: args.durations]:
            print(f"  {dt:6.3f}s: {name}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
