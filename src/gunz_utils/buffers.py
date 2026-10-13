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
        data parameter.

    Returns
    -------
    memoryview
        The result of the operation.
    """
    if not isinstance(data, bytes | bytearray | memoryview):
        raise TypeError(
            "as_readonly_view requires bytes, bytearray, or memoryview input, "
            f"got {type(data).__name__}"
        )
    try:
        view = memoryview(data).cast("B")
    except TypeError:
        #? A non-contiguous (stepped) memoryview slice cannot be cast to a
        #? byte view zero-copy. Fall back to a copy of the logical bytes so a
        #? readonly byte view is still returned for any accepted bytes-like
        #? input.
        view = memoryview(bytes(data))
    return view.toreadonly()


def dispatch(
    reference: Callable[..., T],
    accelerated: Callable[..., T] | None = None,
) -> Callable[..., T]:
    """Select an optional accelerated implementation without making it required.

    Parameters
    ----------
    reference : Callable[..., T]
        reference parameter.
    accelerated : Callable[..., T] | None
        accelerated parameter.

    Returns
    -------
    Callable[..., T]
        The result of the operation.
    """
    return accelerated or reference


__all__ = ["as_readonly_view", "dispatch"]
