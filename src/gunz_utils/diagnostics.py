"""Safe exception diagnostics."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .redaction import redact_dict


def _json_safe(
    value: Any,
) -> Any:
    """Recursively coerce a value to a JSON-serializable form.

    Sets become sorted lists, bytes become a repr string, and any other
    non-serializable object becomes its repr, so the diagnostics envelope can
    always be encoded with ``json.dumps``.
    """
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, set | frozenset):
        return sorted(
            (_json_safe(item) for item in value),
            key=repr,
        )
    if isinstance(value, bytes | bytearray | memoryview):
        return repr(bytes(value))
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return repr(value)
        return value
    return repr(value)


def exception_dict(
    exc: BaseException,
    *,
    context: dict[str, Any] | None = None,
    include_message: bool = False,
) -> dict[str, Any]:
    """Return a JSON-friendly exception envelope with redacted context.

    Raw exception messages are excluded by default because exception text can
    contain submitted values, URLs, credentials, or third-party diagnostics.
    Callers may opt in only when the exception source is trusted.
    """
    if not isinstance(include_message, bool):
        raise TypeError("include_message must be bool")
    result: dict[str, Any] = {
        "type": type(exc).__name__,
    }
    if include_message:
        result["message"] = str(exc)
    if context is not None:
        result["context"] = _json_safe(redact_dict(context, show_chars=0))
    return result


__all__ = ["exception_dict"]
