"""
Optional backend implementations of gunz-utils modules.

Importing from this package never fails — each submodule is independent.
If you need the pydantic-backed default of `type_checked`, use:

    from gunz_utils import type_checked

If you want the stdlib fallback (no pydantic runtime cost):

    from gunz_utils.ext.validation_stdlib import type_checked

Same shape for project / observability / secure modules.
"""
from __future__ import annotations

__all__: list[str] = []