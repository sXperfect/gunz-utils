"""Identifier helpers."""

from __future__ import annotations

import hashlib
import uuid


def new_id() -> str:
    """Return a random UUID4 identifier as canonical text."""
    return str(uuid.uuid4())


def deterministic_id(namespace: str, value: str) -> str:
    """Return a stable UUID5 identifier for a namespace/value pair."""
    if not isinstance(namespace, str) or not isinstance(value, str):
        raise TypeError("namespace and value must be strings")
    ns = uuid.uuid5(uuid.NAMESPACE_URL, namespace)
    return str(uuid.uuid5(ns, value))


def short_id(value: str, *, length: int = 12) -> str:
    """Return a deterministic compact identifier for display and keys."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    if isinstance(length, bool) or not isinstance(length, int) or length < 4 or length > 64:
        raise ValueError("length must be between 4 and 64")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


__all__ = ["deterministic_id", "new_id", "short_id"]
