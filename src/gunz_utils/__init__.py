"""Shared low-level python utilities for the Gunz ecosystem."""

from .enums import BaseStrEnum, BaseIntEnum, OptionalBaseStrEnum
from .security import sanitize_filename, safe_path_join
from .upstream_protocol import (
    UpstreamClient,
    BaseUpstream,
    UpstreamError,
    UpstreamTimeoutError,
    UpstreamAuthError,
    UpstreamNotFoundError,
    UpstreamUnavailableError,
)
from .models import HealthStatus

__version__ = "1.1.0"

_LAZY: dict[str, str] = {
    "type_checked": ".ext.validation_pydantic",
    "resolve_project_root": ".ext.project_gitpython",
    "setup_logging": ".ext.observability_loguru",
    "encrypt": ".ext.secure_crypto",
    "decrypt": ".ext.secure_crypto",
    "get_derived_key": ".ext.secure_crypto",
    "get_system_passphrase": ".ext.secure_crypto",
    "SecureStore": ".ext.secure_store",
    "SecretMetadata": ".ext.secure_store",
}


def __getattr__(name: str):
    """PEP 562 lazy module attribute resolution.

    Names listed in `_LAZY` are loaded on first access via the named
    submodule under `gunz_utils.ext.*`. Anything else raises
    `AttributeError` with the conventional message.
    """
    if name not in _LAZY:
        raise AttributeError(f"module 'gunz_utils' has no attribute {name!r}")
    import importlib
    return getattr(importlib.import_module(_LAZY[name], __name__), name)


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(_LAZY.keys()))


__all__ = [
    "BaseIntEnum",
    "BaseStrEnum",
    "OptionalBaseStrEnum",
    "sanitize_filename",
    "safe_path_join",
    "UpstreamClient",
    "BaseUpstream",
    "UpstreamError",
    "UpstreamTimeoutError",
    "UpstreamAuthError",
    "UpstreamNotFoundError",
    "UpstreamUnavailableError",
    "HealthStatus",
    "type_checked",
    "resolve_project_root",
    "setup_logging",
    "encrypt",
    "decrypt",
    "get_derived_key",
    "get_system_passphrase",
    "SecureStore",
    "SecretMetadata",
    "__version__",
]