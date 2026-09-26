"""Shared low-level python utilities for the Gunz ecosystem."""

from __future__ import annotations

from typing import Any

from .cache import SingleFlight, ttl_cache
from .concurrency import gather_limited, map_concurrent
from .dict_utils import deep_get, deep_merge, deep_set
from .enums import BaseIntEnum, BaseStrEnum, OptionalBaseStrEnum
from .formatting import format_bytes, format_count, format_duration
from .hashing import (
    DEFAULT_ALGO,
    DEFAULT_CHUNK_SIZE,
    SUPPORTED_ALGOS,
    content_hash,
    file_hash,
    short_hash,
)
from .io import atomic_write
from .iteration import batched, chunked, first, flatten
from .parsing import parse_bool, safe_bool, safe_float, safe_int
from .redaction import SECRET_PATTERNS, redact, redact_dict
from .retry import async_retry, retry
from .security import open_path_under_base, safe_path_join, sanitize_filename
from .serialization import canonical_json, json_dumps, json_loads, to_jsonable
from .subprocess import CommandError, CommandResult, run_command, run_command_async
from .timing import Timer, timer
from .upstream_protocol import (
    BaseUpstream,
    PolicyUpstream,
    UpstreamAuthError,
    UpstreamClient,
    UpstreamError,
    UpstreamNotFoundError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

__version__ = "1.8.0"

_LAZY: dict[str, str] = {
    "GunzBaseModel": ".models",
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


def __getattr__(name: str) -> Any:
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
    "SingleFlight",
    "ttl_cache",
    "gather_limited",
    "map_concurrent",
    "retry",
    "async_retry",
    "canonical_json",
    "json_dumps",
    "json_loads",
    "to_jsonable",
    "CommandError",
    "CommandResult",
    "run_command",
    "run_command_async",
    "BaseIntEnum",
    "BaseStrEnum",
    "OptionalBaseStrEnum",
    "atomic_write",
    "batched",
    "chunked",
    "content_hash",
    "DEFAULT_ALGO",
    "DEFAULT_CHUNK_SIZE",
    "deep_get",
    "deep_merge",
    "deep_set",
    "file_hash",
    "first",
    "flatten",
    "format_bytes",
    "format_count",
    "format_duration",
    "parse_bool",
    "safe_bool",
    "safe_float",
    "safe_int",
    "sanitize_filename",
    "open_path_under_base",
    "safe_path_join",
    "SECRET_PATTERNS",
    "redact",
    "redact_dict",
    "short_hash",
    "SUPPORTED_ALGOS",
    "Timer",
    "timer",
    "UpstreamClient",
    "BaseUpstream",
    "PolicyUpstream",
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
