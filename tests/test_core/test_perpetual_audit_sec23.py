"""Perpetual security & concurrency audit - PHASE 23 (round-3) regression tests.

Round-3 re-audit of secure_crypto, secure_store, observability_loguru, and
project_stdlib (the deepest deferred/NEW issues two prior passes missed). Tests
are written to FAIL ("red") against the current source (base 79067b6, which
already contains the phase 1-22 fixes) and must pass only after the
corresponding production fix lands. Production code is intentionally not
modified.

Findings covered here (NEW, not previously flagged):

1. ``project_stdlib.resolve_project_root`` (ext/project_stdlib.py:68-97) has the
   same process-global cache short-circuit as the gitpython backend: once a root
   is cached, any later anchor at-or-below it reuses the cache without checking
   for a nested repo boundary between them. The gitpython analog was fixed in
   phase 20, but this stdlib module was not, so resolving an outer repo first
   and then an anchor inside a nested repo returns the OUTER root - a silent
   wrong result (path corners).

2. ``observability_loguru.setup_logging`` (ext/observability_loguru.py:122-138)
   guards the ``logs/`` DIRECTORY against symlinks (lines 125-129) but does NOT
   guard the log FILE path ``log_dir / f"{log_name}.log"``. A symlink planted at
   that exact path is followed by the loguru file handler, so log output is
   written (appended) into the symlink target - e.g. a sensitive file outside
   ``logs/`` - defeating the module's own symlink-defense intent.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import os
import pathlib
import tempfile
import time

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

# -----------------------------------------------------------------------------
# project_stdlib.py - cache short-circuits nested repos
# -----------------------------------------------------------------------------


def test_project_stdlib_nested_repo_returns_inner_root() -> None:
    """RED: a nested repo anchor must resolve to its own root, not the outer one."""
    import gunz_utils.ext.project_stdlib as project_stdlib

    project_stdlib._PROJECT_ROOT = None
    project_stdlib._PROJECT_ANCHOR = None

    with tempfile.TemporaryDirectory() as tmp:
        outer = pathlib.Path(tmp) / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        nested = outer / "nested"
        nested.mkdir()
        (nested / ".git").mkdir()

        resolve = project_stdlib.resolve_project_root
        outer_root = resolve(anchor=str(outer), inject_to_sys_path=False)
        inner_root = resolve(anchor=str(nested), inject_to_sys_path=False)

        assert nested.resolve() == inner_root
        assert inner_root != outer_root


def test_project_stdlib_same_repo_descendant_uses_cache() -> None:
    """Sanity green: a plain same-repo descendant still resolves to the outer root."""
    import gunz_utils.ext.project_stdlib as project_stdlib

    project_stdlib._PROJECT_ROOT = None
    project_stdlib._PROJECT_ANCHOR = None

    with tempfile.TemporaryDirectory() as tmp:
        outer = pathlib.Path(tmp) / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        sub = outer / "sub"
        sub.mkdir()

        resolve = project_stdlib.resolve_project_root
        outer_root = resolve(anchor=str(outer), inject_to_sys_path=False)
        sub_root = resolve(anchor=str(sub), inject_to_sys_path=False)

        assert sub_root == outer_root


# -----------------------------------------------------------------------------
# observability_loguru.py - log file path not guarded against symlinks
# -----------------------------------------------------------------------------


def test_setup_logging_rejects_symlinked_log_file() -> None:
    """RED: a symlink at the log file path must not redirect log writes into it."""
    pytest.importorskip("loguru")
    from loguru import logger

    from gunz_utils.ext.observability_loguru import setup_logging

    with tempfile.TemporaryDirectory() as tmp:
        base = pathlib.Path(tmp)
        logs = base / "logs"
        logs.mkdir()
        target = base / "sensitive.txt"
        target.write_text("ORIGINAL")
        os.symlink(target, logs / "app.log")

        logger.remove()
        setup_logging("app", project_root=base)
        logger.info("leaked-log-line")
        time.sleep(0.5)
        logger.remove()

        assert "leaked-log-line" not in target.read_text()
