"""Shared test configuration, fixtures, and marker taxonomy for gunz-utils.

Marker Taxonomy:
- ``@pytest.mark.slow``: Tests taking >0.5s or running stress loops,
  concurrency, or large matrices.
- ``@pytest.mark.integration``: Tests verifying end-to-end interactions
  across multiple modules.
- ``@pytest.mark.policy``: Tests validating repository contracts, AGENTS.md,
  or CI/release workflows.
- ``@pytest.mark.isolation``: Packaging and clean-venv dependency-isolation
  matrix tests.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the resolved root directory of the repository."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def compatible_procfs() -> None:
    """Require real procfs observations to use this process's PID namespace."""
    try:
        proc_pid = int(Path("/proc/self/stat").read_bytes().split(b" ", 1)[0])
    except (OSError, ValueError):
        pytest.skip("real process profiling requires readable Linux /proc/self/stat")
    if proc_pid != os.getpid():
        pytest.skip(
            "real process profiling requires procfs in the same PID namespace "
            f"(procfs PID {proc_pid}, process PID {os.getpid()})"
        )
