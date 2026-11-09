"""Identifier helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import hashlib
import uuid


def new_id() -> str:
    """Return a random UUID4 identifier as canonical text.

    Returns
    -------
    str
        The result of the operation.
    """
    return str(uuid.uuid4())


def deterministic_id(
    namespace: str,
    value: str,
) -> str:
    """Return a stable UUID5 identifier for a namespace/value pair.

    Parameters
    ----------
    namespace : str
        namespace parameter.
    value : str
        value parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    if not isinstance(namespace, str) or not isinstance(value, str):
        raise TypeError("namespace and value must be strings")
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, value))


def short_id(
    value: str | bytes,
    *,
    length: int = 12,
) -> str:
    """Return a deterministic compact identifier for display and keys.

    Parameters
    ----------
    value : str | bytes
        value parameter.
    length : int
        length parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    if not isinstance(value, (str, bytes)):
        raise TypeError("value must be a string or bytes")
    if (
        isinstance(length, bool)
        or not isinstance(length, int)
        or length < 4
        or length > 64
    ):
        raise ValueError("length must be between 4 and 64")
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()[:length]


def is_valid_uuid(
    value: str,
    *,
    version: int | None = None,
) -> bool:
    """Validate whether value is a valid UUID string, optionally checking version.

    Parameters
    ----------
    value : str
        Candidate UUID string.
    version : int | None
        Expected UUID version (1-5) or None.

    Returns
    -------
    bool
        True if value is a valid UUID matching the version requirement.
    """
    if not isinstance(value, str):
        return False
    if version is not None and (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version not in (1, 2, 3, 4, 5)
    ):
        raise ValueError("version must be an integer between 1 and 5 or None")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    if version is not None and parsed.version != version:
        return False
    return True


__all__ = ["deterministic_id", "is_valid_uuid", "new_id", "short_id"]
