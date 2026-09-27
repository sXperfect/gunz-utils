"""Deterministic sampling helpers independent of process hash randomization."""

from __future__ import annotations

import fnmatch
import hashlib
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


def stable_priority(
    name: str,
    *,
    seed: int = 0,
) -> int:
    """Return a process-independent deterministic priority for a name.

    The priority is derived from an 8-byte BLAKE2b digest of the UTF-8 text
    formed from the seed and item name. Unlike Python's built-in hash, the
    result is stable across interpreter processes and hash-randomization seeds.

    Parameters
    ----------
    name : str
        Stable item name.
    seed : int, optional
        Deterministic sampling seed. Default is 0.

    Returns
    -------
    int
        Unsigned 64-bit priority value.

    Raises
    ------
    TypeError
        If name is not a string or seed is not an integer.
    """
    if not isinstance(name, str):
        raise TypeError(f"name must be str, got {type(name).__name__}")
    if not isinstance(seed, int):
        raise TypeError(f"seed must be int, got {type(seed).__name__}")

    payload = f"{seed}:{name}".encode()
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def sample_named_items(
    items: Iterable[tuple[str, T]],
    *,
    limit: int | None,
    seed: int = 0,
    include_patterns: tuple[str, ...] = (),
    exclude_patterns: tuple[str, ...] = (),
) -> list[tuple[str, T]]:
    """Select named items by stable priority after optional glob filtering.

    Parameters
    ----------
    items : Iterable[tuple[str, T]]
        Named values to sample.
    limit : int | None
        Maximum returned items. None returns every eligible item and zero
        returns an empty list.
    seed : int, optional
        Deterministic sampling seed. Default is 0.
    include_patterns : tuple[str, ...], optional
        If non-empty, an item name must match at least one fnmatch pattern.
    exclude_patterns : tuple[str, ...], optional
        Item names matching any pattern are excluded.

    Returns
    -------
    list[tuple[str, T]]
        Eligible items ordered by deterministic priority then name.

    Raises
    ------
    ValueError
        If limit is negative or item names are duplicated.
    TypeError
        If an item name is not a string.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")

    eligible: list[tuple[str, T]] = []
    seen_names: set[str] = set()
    for name, value in items:
        if not isinstance(name, str):
            raise TypeError(
                f"item name must be str, got {type(name).__name__}"
            )
        if name in seen_names:
            raise ValueError(
                f"duplicate item name is not deterministic: {name!r}"
            )
        seen_names.add(name)
        if include_patterns and not any(
            fnmatch.fnmatchcase(name, pattern)
            for pattern in include_patterns
        ):
            continue
        if exclude_patterns and any(
            fnmatch.fnmatchcase(name, pattern)
            for pattern in exclude_patterns
        ):
            continue
        eligible.append((name, value))

    eligible.sort(
        key=lambda item: (
            stable_priority(item[0], seed=seed),
            item[0],
        )
    )
    return eligible if limit is None else eligible[:limit]


__all__ = ["sample_named_items", "stable_priority"]
