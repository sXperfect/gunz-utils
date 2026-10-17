"""Directory-level test configuration for optional secure store tests."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import importlib.util
from typing import Any

_HAS_CRYPTOGRAPHY = importlib.util.find_spec("cryptography") is not None


def pytest_ignore_collect(
    collection_path: Any,
    config: Any,
) -> bool:
    """Ignore all files in test_secure if cryptography extra is not installed."""
    del collection_path, config
    return not _HAS_CRYPTOGRAPHY
