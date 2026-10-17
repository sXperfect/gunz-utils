"""Directory-level test configuration for optional project tests."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
from typing import Any

_HAS_GIT = importlib.util.find_spec("git") is not None


def pytest_ignore_collect(
    collection_path: Any,
    config: Any,
) -> bool:
    """Ignore all files in test_project if GitPython extra is not installed."""
    del collection_path, config
    return not _HAS_GIT
