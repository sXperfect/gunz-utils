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

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the resolved root directory of the repository."""
    return PROJECT_ROOT
