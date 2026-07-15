"""
Shared low-level python utilities for the Gunz ecosystem.

Lazy import shim (PEP 562): heavy third-party dependencies
(``gitpython``, ``loguru``, ``cryptography``) are deferred until
the corresponding symbol is first accessed. This lets light-weight
consumers (e.g. ``gunz_utils.upstream_protocol``, which only needs
stdlib) import this package without installing every transitive
dependency.

This file is the 2026-07-15 port of the design pattern originally
preserved in ``hyperhedron-youtrack``'s vendored snapshot
(recoverable from ``hyperhedron-youtrack-pre-filter-repo-snapshots``)
back into the sibling source. It supersedes the prior eager-import
``__init__.py`` of sibling's local main, which forced every consumer
of ``gunz_utils`` to pay the import cost of every transitive dep.

Public API
----------

From the original v1.0.0 surface (eager where cheap, lazy where heavy)::

    from gunz_utils import (
        BaseStrEnum, BaseIntEnum, OptionalBaseStrEnum,   # from .enums
        type_checked,                                    # from .validation
        sanitize_filename, safe_path_join,               # from .security
        resolve_project_root,                            # from .project
    )

From the Phase 1.2 UpstreamClient Protocol::

    from gunz_utils import (
        UpstreamClient, BaseUpstream,
        UpstreamError, UpstreamTimeoutError,
        UpstreamAuthError, UpstreamNotFoundError,
        UpstreamUnavailableError,
    )

From the Phase 6.1 Fernet-encrypted secret store::

    from gunz_utils import SecureStore, SecretMetadata

Backward compatibility note: the previous ``__init__.py`` imported
these symbols eagerly. Code that does ``import gunz_utils`` and then
``gunz_utils.resolve_project_root`` continues to work — the symbol
is loaded on first attribute access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Static type-checkers see the eager form; runtime uses __getattr__.
    from .enums import BaseIntEnum, BaseStrEnum, OptionalBaseStrEnum
    from .project import resolve_project_root
    from .security import safe_path_join, sanitize_filename
    from .upstream_protocol import (
        BaseUpstream,
        UpstreamAuthError,
        UpstreamClient,
        UpstreamError,
        UpstreamNotFoundError,
        UpstreamTimeoutError,
        UpstreamUnavailableError,
    )
    from .validation import type_checked


# Map of public name -> (submodule, attribute). PEP 562 lazy attribute
# resolution: the actual import only fires when something accesses
# the attribute on the package.
_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    # Original v1.0.0 API
    "BaseStrEnum":                ("enums",            "BaseStrEnum"),
    "BaseIntEnum":                ("enums",            "BaseIntEnum"),
    "OptionalBaseStrEnum":        ("enums",            "OptionalBaseStrEnum"),
    "type_checked":               ("validation",       "type_checked"),
    "sanitize_filename":          ("security",         "sanitize_filename"),
    "safe_path_join":             ("security",         "safe_path_join"),
    "resolve_project_root":       ("project",          "resolve_project_root"),
    # Phase 1.2 additions (UpstreamClient Protocol)
    "UpstreamClient":             ("upstream_protocol", "UpstreamClient"),
    "BaseUpstream":               ("upstream_protocol", "BaseUpstream"),
    "UpstreamError":              ("upstream_protocol", "UpstreamError"),
    "UpstreamTimeoutError":       ("upstream_protocol", "UpstreamTimeoutError"),
    "UpstreamAuthError":          ("upstream_protocol", "UpstreamAuthError"),
    "UpstreamNotFoundError":      ("upstream_protocol", "UpstreamNotFoundError"),
    "UpstreamUnavailableError":   ("upstream_protocol", "UpstreamUnavailableError"),
    # Phase 6.1 additions (Fernet-encrypted secret store)
    "SecureStore":                ("secure_store",     "SecureStore"),
    "SecretMetadata":             ("secure_store",     "SecretMetadata"),
    "default_base_dir":           ("secure_store",     "default_base_dir"),
    "main_unlock_interactive":    ("secure_store",     "main_unlock_interactive"),
}


def __getattr__(name: str):
    """Lazy attribute resolution (PEP 562)."""
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}. "
            f"Known public names: {sorted(_LAZY_ATTRS)}"
        )
    submodule, attr = target
    from importlib import import_module

    mod = import_module(f".{submodule}", __name__)
    value = getattr(mod, attr)
    # Cache on the package so subsequent lookups skip import_module.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY_ATTRS.keys()))


__version__ = "1.2.0"

__all__ = [
    # v1.0.0 API
    "BaseStrEnum",
    "BaseIntEnum",
    "OptionalBaseStrEnum",
    "type_checked",
    "sanitize_filename",
    "safe_path_join",
    "resolve_project_root",
    # Phase 1.2 additions
    "UpstreamClient",
    "BaseUpstream",
    "UpstreamError",
    "UpstreamTimeoutError",
    "UpstreamAuthError",
    "UpstreamNotFoundError",
    "UpstreamUnavailableError",
    # Phase 6.1 additions
    "SecureStore",
    "SecretMetadata",
    "default_base_dir",
    "main_unlock_interactive",
]
