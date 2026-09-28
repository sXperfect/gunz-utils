"""Safe exception diagnostics."""

from __future__ import annotations

from typing import Any

from .redaction import redact_dict


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
        result["context"] = redact_dict(context, show_chars=0)
    return result


__all__ = ["exception_dict"]
