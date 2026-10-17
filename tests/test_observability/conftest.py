"""Directory-level test configuration for optional observability tests."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
from typing import Any

_HAS_LOGURU = importlib.util.find_spec("loguru") is not None


def pytest_ignore_collect(
    collection_path: Any,
    config: Any,
) -> bool:
    """Ignore all files in test_observability if loguru extra is not installed."""
    del collection_path, config
    return not _HAS_LOGURU
