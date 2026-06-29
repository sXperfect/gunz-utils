"""Shared low-level python utilities for the Gunz ecosystem."""

from .enums import BaseStrEnum, BaseIntEnum, OptionalBaseStrEnum
from .project import resolve_project_root
from .security import safe_path_join, sanitize_filename
from .validation import type_checked

# ? Single source of truth for the package version. Submodules
# ? (enums.py, validation.py, etc.) each have their own __version__
# ? dunder that should match this — kept in sync by a release script
# ? or by reading this value (future work).
__version__ = "1.0.0"

__all__ = [
    "BaseIntEnum",
    "BaseStrEnum",
    "OptionalBaseStrEnum",
    "__version__",
    "resolve_project_root",
    "safe_path_join",
    "sanitize_filename",
    "type_checked",
]
