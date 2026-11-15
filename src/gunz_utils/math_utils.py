"""Pure-Python numerical primitives, vector math, and combinatorics."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Iterator, Sequence
from typing import TypeVar

T = TypeVar("T")


def dot_product(
    u: Sequence[float],
    v: Sequence[float],
) -> float:
    """Compute the scalar dot product of two numerical vectors."""
    if len(u) != len(v):
        raise ValueError(f"vectors must have the same length: {len(u)} != {len(v)}")
    return sum(a * b for a, b in zip(u, v))


def vector_norm(
    v: Sequence[float],
    p: float = 2.0,
) -> float:
    """Compute the Lp norm of a vector (default L2 Euclidean norm)."""
    if not v:
        return 0.0
    if p == 2.0:
        return math.sqrt(sum(x * x for x in v))
    if p == 1.0:
        return sum(abs(x) for x in v)
    if math.isinf(p) and p > 0:
        return max(abs(x) for x in v)
    if p <= 0:
        raise ValueError("p norm must be positive or infinity")
    return sum(abs(x) ** p for x in v) ** (1.0 / p)


def vector_normalize(
    v: Sequence[float],
) -> list[float]:
    """Normalize a vector to unit length (Euclidean L2 norm)."""
    norm = vector_norm(v, p=2.0)
    if norm == 0.0:
        raise ValueError("cannot normalize a zero vector")
    return [x / norm for x in v]


def cosine_similarity(
    u: Sequence[float],
    v: Sequence[float],
) -> float:
    """Compute the cosine similarity between two vectors in [-1.0, 1.0]."""
    if len(u) != len(v):
        raise ValueError(f"vectors must have the same length: {len(u)} != {len(v)}")
    norm_u = vector_norm(u, 2.0)
    norm_v = vector_norm(v, 2.0)
    if norm_u == 0.0 or norm_v == 0.0:
        return 0.0
    sim = dot_product(u, v) / (norm_u * norm_v)
    return max(-1.0, min(1.0, sim))


def lerp(
    a: float,
    b: float,
    t: float,
) -> float:
    """Linear interpolation between a and b by factor t."""
    return a + (b - a) * t


def inverse_lerp(
    a: float,
    b: float,
    value: float,
) -> float:
    """Compute normalized t factor where lerp(a, b, t) == value."""
    if a == b:
        return 0.0
    return (value - a) / (b - a)


def clamp(
    value: float,
    min_val: float,
    max_val: float,
) -> float:
    """Clamp a numerical value between lower and upper bounds."""
    if min_val > max_val:
        raise ValueError("min_val cannot be greater than max_val")
    return max(min_val, min(value, max_val))


def smoothstep(
    edge0: float,
    edge1: float,
    x: float,
) -> float:
    """Smooth Hermite interpolation between 0 and 1 when edge0 <= x <= edge1."""
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def gcd_multiple(
    *numbers: int,
) -> int:
    """Compute the greatest common divisor of one or more integers."""
    if not numbers:
        raise ValueError("at least one number must be provided")
    return math.gcd(*numbers)


def lcm(
    a: int,
    b: int,
) -> int:
    """Compute the least common multiple of two integers."""
    return math.lcm(a, b)


def lcm_multiple(
    *numbers: int,
) -> int:
    """Compute the least common multiple of one or more integers."""
    if not numbers:
        raise ValueError("at least one number must be provided")
    return math.lcm(*numbers)


def is_prime(
    n: int,
) -> bool:
    """Deterministic primality test for 64-bit integers using Miller-Rabin."""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    #? Miller-Rabin with deterministic bases for 64-bit integers
    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1

    bases = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for a in bases:
        if n <= a:
            break
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        composite = True
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                composite = False
                break
        if composite:
            return False
    return True


def prime_factors(
    n: int,
) -> list[int]:
    """Return the prime factorization of a positive integer in ascending order."""
    if n < 1:
        raise ValueError("n must be a positive integer")
    factors: list[int] = []
    #? 2s
    while n % 2 == 0:
        factors.append(2)
        n //= 2
    #? odds
    d = 3
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 2
    if n > 1:
        factors.append(n)
    return factors


def powerset(
    iterable: Iterable[T],
) -> Iterator[tuple[T, ...]]:
    """Generate all subsets of an iterable from length 0 to N."""
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(len(s) + 1))


__all__ = [
    "clamp",
    "cosine_similarity",
    "dot_product",
    "gcd_multiple",
    "inverse_lerp",
    "is_prime",
    "lcm",
    "lcm_multiple",
    "lerp",
    "powerset",
    "prime_factors",
    "smoothstep",
    "vector_norm",
    "vector_normalize",
]
