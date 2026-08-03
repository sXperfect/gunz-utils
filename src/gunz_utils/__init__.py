"""Shared low-level python utilities for the Gunz ecosystem."""

from .enums import BaseIntEnum, BaseStrEnum, OptionalBaseStrEnum
from .formatting import format_bytes, format_count, format_duration
from .io import atomic_write
from .models import GunzBaseModel
from .parsing import parse_bool, safe_bool, safe_float, safe_int
from .redaction import SECRET_PATTERNS, redact, redact_dict
from .security import safe_path_join, sanitize_filename
from .timing import Timer, timer
from .upstream_protocol import (
    BaseUpstream,
    UpstreamAuthError,
    UpstreamClient,
    UpstreamError,
    UpstreamNotFoundError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

__version__ = "1.7.0"

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
    "atomic_write",
    "format_bytes",
    "format_count",
    "format_duration",
    "parse_bool",
    "safe_bool",
    "safe_float",
    "safe_int",
    "sanitize_filename",
    "safe_path_join",
    "SECRET_PATTERNS",
    "redact",
    "redact_dict",
    "Timer",
    "timer",
    "UpstreamClient",
    "BaseUpstream",
    "UpstreamError",
    "UpstreamTimeoutError",
    "UpstreamAuthError",
    "UpstreamNotFoundError",
    "UpstreamUnavailableError",
    "GunzBaseModel",
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
