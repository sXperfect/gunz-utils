"""Safe exception diagnostics."""

from __future__ import annotations

from typing import Any

from .redaction import redact_dict


def exception_dict(
    exc: BaseException,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a JSON-friendly exception envelope with redacted context."""
    result: dict[str, Any] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    if context is not None:
        result["context"] = redact_dict(context, show_chars=0)
    return result


__all__ = ["exception_dict"]
