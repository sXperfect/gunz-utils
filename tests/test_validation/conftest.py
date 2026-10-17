"""Directory-level test configuration for optional validation tests."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
from typing import Any

_HAS_PYDANTIC = importlib.util.find_spec("pydantic") is not None


def pytest_ignore_collect(
    collection_path: Any,
    config: Any,
) -> bool:
    """Ignore all files in test_validation if pydantic extra is not installed."""
    del collection_path, config
    return not _HAS_PYDANTIC
