"""Safe exception diagnostics."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .redaction import redact, redact_dict


def exception_dict(
    exc: BaseException,
    *,
    context: Mapping[str, Any] | None = None,
    include_message: bool = False,
) -> dict[str, Any]:
    """Return a JSON-friendly exception envelope with redacted context.

    Raw exception messages are excluded by default because exception text can
    contain submitted values, URLs, credentials, or third-party diagnostics.
    When included, message text is passed through the secret redactor.
    """
    if not isinstance(exc, BaseException):
        raise TypeError("exc must be a BaseException")
    if not isinstance(include_message, bool):
        raise TypeError("include_message must be bool")
    if context is not None and not isinstance(context, Mapping):
        raise TypeError("context must be a Mapping or None")
    result: dict[str, Any] = {
        "type": type(exc).__name__,
    }
    if include_message:
        result["message"] = str(exc)
    if context is not None:
        result["context"] = redact_dict(dict(context), show_chars=0)
    return result


__all__ = ["exception_dict"]
