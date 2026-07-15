"""Backwards-compat shim re-exporting from ext.validation_pydantic.

The canonical implementation lives at ``gunz_utils.ext.validation_pydantic``
following the v1.3.0 dependency split (see CHANGELOG.md). This thin shim
preserves the historical import path ``from gunz_utils.validation import …``
for callers that have not yet migrated.

New code SHOULD import from the canonical location or from the public
package surface (``from gunz_utils import type_checked``).
"""
from __future__ import annotations

from gunz_utils.ext.validation_pydantic import (
    type_checked,
    validate_call,
)

__all__ = ["type_checked", "validate_call"]
