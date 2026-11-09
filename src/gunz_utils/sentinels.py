"""
Sentinel values for distinguishing "not supplied" from an explicit value.

An unset/missing sentinel answers a different question from ``None``: it means
"the caller did not pass this argument", whereas ``None`` is a genuine value a
caller may legitimately want to store. Use the singleton ``UNSET`` in default
positions and test with ``value is UNSET`` (or the ``is_unset`` helper).
"""

from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
from typing import TypeVar

T = TypeVar("T")


class UnsetType:
    """Singleton type whose only instance is the ``UNSET`` sentinel.

    ``UNSET`` is safe to use as a default because identity comparison
    (``value is UNSET``) can never collide with any caller-supplied value,
    including ``None``, booleans, and other falsy values.
    """

    _instance: "UnsetType | None" = None

    def __new__(
        cls,
    ) -> "UnsetType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(
        self,
    ) -> str:
        return "UNSET"

    def __bool__(
        self,
    ) -> bool:
        return False

    def __reduce__(
        self,
    ) -> tuple[type, tuple]:
        #? Return (class, ()) so pickling and unpickling reconstruct the same
        #? singleton across process boundaries (e.g. training workers).
        return (UnsetType, ())


UNSET = UnsetType()


def is_unset(
    value: object,
) -> bool:
    """Return True when ``value`` is the ``UNSET`` sentinel.

    Parameters
    ----------
    value : object
        The value to test.

    Returns
    -------
    bool
        True when ``value`` is the ``UNSET`` sentinel, False otherwise.
    """
    return value is UNSET


def default(
    value: T | UnsetType,
    fallback: T,
) -> T:
    """Return ``fallback`` when ``value`` is unset, else ``value``.

    Parameters
    ----------
    value : T or UnsetType
        A value or the ``UNSET`` sentinel.
    fallback : T
        The value to return when ``value`` is ``UNSET``.

    Returns
    -------
    T
        ``fallback`` if ``value`` is ``UNSET``, otherwise ``value``.
    """
    return fallback if value is UNSET else value


__all__ = ["UNSET", "UnsetType", "default", "is_unset"]
