"""Tests for Wave 6 Sub-Wave 1: Numerical Primitives, Vector Math & Combinatorics."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import math

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.math_utils import (
    clamp,
    cosine_similarity,
    dot_product,
    gcd_multiple,
    inverse_lerp,
    is_prime,
    lcm,
    lcm_multiple,
    lerp,
    powerset,
    prime_factors,
    smoothstep,
    vector_norm,
    vector_normalize,
)


def test_vector_math():
    u = [1.0, 2.0, 3.0]
    v = [4.0, 5.0, 6.0]
    assert dot_product(u, v) == 1 * 4 + 2 * 5 + 3 * 6
    assert vector_norm([3.0, 4.0], p=2.0) == 5.0
    assert vector_norm([3.0, -4.0], p=1.0) == 7.0
    assert vector_norm([3.0, -4.0], p=float("inf")) == 4.0

    normalized = vector_normalize([3.0, 4.0])
    assert math.isclose(normalized[0], 0.6)
    assert math.isclose(normalized[1], 0.8)

    sim = cosine_similarity([1.0, 0.0], [0.0, 1.0])
    assert math.isclose(sim, 0.0)
    sim_same = cosine_similarity([2.0, 2.0], [4.0, 4.0])
    assert math.isclose(sim_same, 1.0)


def test_interpolation_and_clamp():
    assert lerp(10.0, 20.0, 0.5) == 15.0
    assert inverse_lerp(10.0, 20.0, 15.0) == 0.5
    assert clamp(15.0, 0.0, 10.0) == 10.0
    assert clamp(-5.0, 0.0, 10.0) == 0.0
    assert clamp(5.0, 0.0, 10.0) == 5.0

    assert smoothstep(0.0, 10.0, -1.0) == 0.0
    assert smoothstep(0.0, 10.0, 11.0) == 1.0
    assert smoothstep(0.0, 10.0, 5.0) == 0.5


def test_gcd_lcm_primes():
    assert gcd_multiple(24, 36, 48) == 12
    assert lcm(4, 6) == 12
    assert lcm_multiple(2, 3, 4, 5) == 60

    assert not is_prime(0)
    assert not is_prime(1)
    assert is_prime(2)
    assert is_prime(3)
    assert not is_prime(4)
    assert is_prime(97)
    assert not is_prime(100)
    assert is_prime(104729)

    assert prime_factors(60) == [2, 2, 3, 5]
    assert prime_factors(97) == [97]


def test_powerset():
    subsets = list(powerset([1, 2]))
    assert subsets == [(), (1,), (2,), (1, 2)]
