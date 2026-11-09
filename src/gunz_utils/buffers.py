"""Zero-copy buffer utilities and backend dispatch."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def as_readonly_view(
    data: bytes | bytearray | memoryview,
) -> memoryview:
    """Return a byte-oriented readonly view without copying when possible.

    Parameters
    ----------
    data : bytes | bytearray | memoryview
        Binary buffer object.

    Returns
    -------
    memoryview
        Readonly byte-oriented memoryview.

    Raises
    ------
    TypeError
        If data does not support the buffer protocol.
    """
    try:
        view = memoryview(data)
    except TypeError as exc:
        raise TypeError(f"expected a bytes-like object, got {type(data).__name__}") from exc
    try:
        byte_view = view.cast("B")
    except (BufferError, TypeError, ValueError):
        byte_view = memoryview(bytes(view))
    return byte_view.toreadonly()


def dispatch(
    reference: Callable[..., T],
    accelerated: Callable[..., T] | None = None,
) -> Callable[..., T]:
    """Select an optional accelerated implementation without making it required.

    Parameters
    ----------
    reference : Callable[..., T]
        Reference Python implementation.
    accelerated : Callable[..., T] | None
        Accelerated implementation, or None.

    Returns
    -------
    Callable[..., T]
        Accelerated callable if provided, else reference.

    Raises
    ------
    TypeError
        If reference or accelerated is not callable.
    """
    if not callable(reference):
        raise TypeError("reference must be callable")
    if accelerated is not None and not callable(accelerated):
        raise TypeError("accelerated must be callable or None")
    return reference if accelerated is None else accelerated


__all__ = ["as_readonly_view", "dispatch"]
