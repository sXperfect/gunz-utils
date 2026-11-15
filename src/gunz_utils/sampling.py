"""Deterministic sampling helpers independent of process hash randomization."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import fnmatch
import hashlib
import random
from collections.abc import Iterable, Iterator
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
    if isinstance(seed, bool) or not isinstance(seed, int):
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
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError(f"seed must be int, got {type(seed).__name__}")
    if isinstance(limit, bool) or (limit is not None and not isinstance(limit, int)):
        raise TypeError(f"limit must be int or None, got {type(limit).__name__}")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative or None")
    if isinstance(include_patterns, (str, bytes, bytearray)):
        raise TypeError("include_patterns must be an iterable of strings, not a string")
    if isinstance(exclude_patterns, (str, bytes, bytearray)):
        raise TypeError("exclude_patterns must be an iterable of strings, not a string")
    if limit == 0:
        return []

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

    priorities = {name: stable_priority(name, seed=seed) for name, _ in eligible}
    eligible.sort(
        key=lambda item: (
            priorities[item[0]],
            item[0],
        )
    )
    return eligible if limit is None else eligible[:limit]


def reservoir_sample(
    iterable: Iterable[T],
    k: int,
    *,
    rng: random.Random | None = None,
) -> list[T]:
    """Sample k items uniformly from an iterable of unknown length using Algorithm R."""
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise ValueError("k must be a positive integer")
    r = rng if rng is not None else random
    iterator = iter(iterable)
    reservoir: list[T] = []
    for _ in range(k):
        try:
            reservoir.append(next(iterator))
        except StopIteration:
            return reservoir
    for i, item in enumerate(iterator, start=k):
        j = r.randint(0, i)
        if j < k:
            reservoir[j] = item
    return reservoir


def bernoulli_sample(
    iterable: Iterable[T],
    p: float,
    *,
    rng: random.Random | None = None,
) -> Iterator[T]:
    """Yield items independently with probability p."""
    if (
        isinstance(p, bool)
        or not isinstance(p, (int, float))
        or not (0.0 <= p <= 1.0)
    ):
        raise ValueError("p must be a float between 0.0 and 1.0 inclusive")
    r = rng if rng is not None else random
    for item in iterable:
        if r.random() < p:
            yield item


def hash_sample_fraction(
    key: str,
    fraction: float,
    *,
    seed: int = 0,
) -> bool:
    """Deterministically decide if key falls into a sampled fraction based on BLAKE2b hash."""
    if not isinstance(key, str):
        raise TypeError(f"key must be str, got {type(key).__name__}")
    if (
        isinstance(fraction, bool)
        or not isinstance(fraction, (int, float))
        or not (0.0 <= fraction <= 1.0)
    ):
        raise ValueError("fraction must be a float between 0.0 and 1.0 inclusive")
    if fraction == 0.0:
        return False
    if fraction == 1.0:
        return True
    p = stable_priority(key, seed=seed)
    normalized = (p & 0xFFFFFFFFFFFFFFFF) / (2**64)
    return normalized < fraction


__all__ = [
    "bernoulli_sample",
    "hash_sample_fraction",
    "reservoir_sample",
    "sample_named_items",
    "stable_priority",
]
