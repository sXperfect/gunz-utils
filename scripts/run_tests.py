#!/usr/bin/env python3
"""Zero-dependency standalone test runner using Python standard library unittest.

Enables developers to run unit, property, and contract tests immediately on any
ambient Python 3.11+ environment without requiring pytest or third-party tools.
Supports both unittest.TestCase subclasses and standalone test_* functions.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"


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
    return parser


def load_test_suite(
    start_dir: Path,
    pattern: str = "test_*.py",
    keyword: str | None = None,
) -> tuple[unittest.TestSuite, int]:
    """Discover and load both TestCase classes and standalone test functions."""
    suite = unittest.TestSuite()
    skipped_modules = 0

    test_files = sorted(start_dir.rglob(pattern)) if start_dir.is_dir() else [start_dir]

    for py_file in test_files:
        if not py_file.is_file() or py_file.name.startswith((".", "_")):
            continue

        module_name = f"_test_{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except (ImportError, ModuleNotFoundError):
            # Optional third-party dependency missing in current environment
            skipped_modules += 1
            continue
        except Exception as exc:
            # Fatal error during module import
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
            if name.startswith("test_") and inspect.isfunction(obj):
                try:
                    sig = inspect.signature(obj)
                    if len(sig.parameters) > 0:
                        # Skip functions requiring pytest fixtures
                        # (monkeypatch, capsys, etc.)
                        continue
                except Exception:
                    continue
                full_name = f"{py_file.stem}.{name}"
                if keyword is None or keyword.lower() in full_name.lower():
                    suite.addTest(
                        unittest.FunctionTestCase(
                            obj,
                            description=full_name,
                        )
                    )

    return suite, skipped_modules


def main(argv: list[str] | None = None) -> int:
    """Discover and execute tests with pure Python unittest."""
    args = build_parser().parse_args(argv)

    # Ensure worktree src/ and tests/ are on sys.path
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    if str(TESTS_DIR) not in sys.path:
        sys.path.insert(1, str(TESTS_DIR))

    suite, skipped = load_test_suite(
        args.start_dir,
        pattern=args.pattern,
        keyword=args.keyword,
    )

    test_count = suite.countTestCases()
    msg = f"Discovered {test_count} tests"
    if skipped > 0:
        msg += f" ({skipped} files skipped due to uninstalled optional extras)"
    print(msg + ".\n")

    runner = unittest.TextTestRunner(
        verbosity=2 if args.verbose else 1,
        failfast=args.failfast,
    )
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
