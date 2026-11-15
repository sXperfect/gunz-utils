"""Safe exception diagnostics."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import gc
import os
import platform
import re
import sys
import threading
from collections.abc import Mapping
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .redaction import redact_dict

_SECRET_ASSIGN_RE = re.compile(
    r"(?i)(password|secret|token|api_key|access_key|auth|credential)\s*=\s*([\"'][^\"']+[\"'])"
)


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


def format_exception_summary(
    exc: BaseException,
) -> str:
    """Format a compact one-line summary of an exception including type, message, and origin."""
    if not isinstance(exc, BaseException):
        raise TypeError(f"expected BaseException, got {type(exc).__name__}")
    tb = exc.__traceback__
    origin = ""
    if tb is not None:
        while tb.tb_next is not None:
            tb = tb.tb_next
        frame = tb.tb_frame
        filename = os.path.basename(frame.f_code.co_filename)
        lineno = tb.tb_lineno
        origin = f" at {filename}:{lineno}"
    msg = str(exc).strip()
    msg_part = f": {msg}" if msg else ""
    return f"{type(exc).__name__}{msg_part}{origin}"


def capture_system_diagnostics() -> dict[str, Any]:
    """Capture runtime system diagnostics including platform, memory/gc, and threads."""
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "pid": os.getpid(),
        "thread_count": threading.active_count(),
        "gc_counts": gc.get_count(),
    }


def sanitize_traceback(
    tb_str: str,
) -> str:
    """Sanitize secrets and credentials from a traceback string."""
    if not isinstance(tb_str, str):
        raise TypeError(f"expected str, got {type(tb_str).__name__}")
    return _SECRET_ASSIGN_RE.sub(r"\1 = '***'", tb_str)


def get_exception_chain(
    exc: BaseException,
) -> list[BaseException]:
    """Traverse the cause and context chain of an exception safely, preventing infinite loops."""
    if not isinstance(exc, BaseException):
        raise TypeError(f"expected BaseException, got {type(exc).__name__}")
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None:
        ident = id(current)
        if ident in seen:
            break
        seen.add(ident)
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


__all__ = [
    "capture_system_diagnostics",
    "exception_dict",
    "format_exception_summary",
    "get_exception_chain",
    "sanitize_traceback",
]
