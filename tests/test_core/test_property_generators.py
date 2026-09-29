"""Unit and property-based invariant tests for clean-room testkit generators."""

from __future__ import annotations

import copy
import json
import math
from typing import Any

from gunz_utils.cache import ttl_cache
from gunz_utils.hashing import structured_hash
from gunz_utils.redaction import redact
from gunz_utils.structures import deep_diff
from gunz_utils.testkit import (
    PropertyFailure,
    check_property,
    fuzz_bytes,
    fuzz_floats,
    fuzz_integers,
    fuzz_json_objects,
    fuzz_primitives,
    fuzz_strings,
)


def test_fuzz_integers_contract() -> None:
    samples = list(fuzz_integers(seed=123, count=50, minimum=10, maximum=20))
    assert len(samples) == 50
    assert all(10 <= x <= 20 for x in samples)
    # Determinism
    samples2 = list(fuzz_integers(seed=123, count=50, minimum=10, maximum=20))
    assert samples == samples2


def test_fuzz_floats_contract() -> None:
    samples = list(fuzz_floats(seed=42, count=100, minimum=-5.0, maximum=5.0))
    assert len(samples) == 100
    assert all(-5.0 <= x <= 5.0 for x in samples)

    # Special values
    specials = list(
        fuzz_floats(
            seed=42,
            count=100,
            minimum=0.0,
            maximum=1.0,
            allow_nan=True,
            allow_infinity=True,
        )
    )
    has_nan_or_inf = any(math.isnan(x) or math.isinf(x) for x in specials)
    assert has_nan_or_inf


def test_fuzz_strings_and_bytes_contract() -> None:
    str_samples = list(
        fuzz_strings(seed=7, count=50, min_length=5, max_length=15, alphabet="abc")
    )
    assert len(str_samples) == 50
    assert all(5 <= len(s) <= 15 for s in str_samples)
    assert all(all(ch in "abc" for ch in s) for s in str_samples)

    byte_samples = list(fuzz_bytes(seed=99, count=30, min_length=2, max_length=8))
    assert len(byte_samples) == 30
    assert all(isinstance(b, bytes) and 2 <= len(b) <= 8 for b in byte_samples)


def test_fuzz_primitives_contract() -> None:
    samples = list(fuzz_primitives(seed=101, count=100))
    assert len(samples) == 100
    types = {type(s) for s in samples}
    # Should include int, float, str, bool, and NoneType
    assert type(None) in types
    assert bool in types
    assert str in types


def test_fuzz_json_objects_validity() -> None:
    samples = list(fuzz_json_objects(seed=42, count=30, max_depth=3, max_breadth=3))
    assert len(samples) == 30
    for obj in samples:
        assert isinstance(obj, (dict, list))
        # Ensure it is standard JSON serializable
        serialized = json.dumps(obj)
        deserialized = json.loads(serialized)
        assert isinstance(deserialized, (dict, list))


def test_check_property_success() -> None:
    def is_even(n: int) -> bool:
        return n % 2 == 0

    evens = (i * 2 for i in range(100))
    passed = check_property(evens, is_even, max_examples=50)
    assert passed == 50


def test_check_property_failure_handling() -> None:
    def reject_fives(n: int) -> bool:
        return n != 5

    numbers = range(10)
    try:
        check_property(numbers, reject_fives, seed=123)
        assert False, "Should have raised PropertyFailure"
    except PropertyFailure as err:
        assert err.iteration == 5
        assert err.sample == 5
        assert err.seed == 123


def test_check_property_exception_handling() -> None:
    def boom_on_zero(n: int) -> None:
        if n == 0:
            raise ValueError("zero not allowed")

    candidates = [1, 2, 0, 3]
    try:
        check_property(candidates, boom_on_zero)
        assert False, "Should have raised PropertyFailure"
    except PropertyFailure as err:
        assert err.iteration == 2
        assert err.sample == 0
        assert isinstance(err.cause, ValueError)


def test_invariant_deep_diff_reflexivity() -> None:
    """Verify that deep_diff(x, x) is always empty for arbitrary JSON structures."""
    seed = 888
    generator = fuzz_json_objects(seed=seed, count=50, max_depth=3, max_breadth=4)

    def assert_reflexive(obj: Any) -> None:
        diff = deep_diff(obj, obj)
        assert diff == [], f"Reflexivity violated for sample: {diff}"

    checked = check_property(generator, assert_reflexive, max_examples=50, seed=seed)
    assert checked == 50


def test_invariant_structured_hash_stability() -> None:
    """Verify that structured_hash is deterministic and value-equivalent."""
    seed = 999
    generator = fuzz_json_objects(seed=seed, count=50, max_depth=3, max_breadth=3)

    def assert_deterministic_hash(obj: Any) -> None:
        h1 = structured_hash(obj)
        h2 = structured_hash(copy.deepcopy(obj))
        assert h1 == h2
        assert isinstance(h1, str) and len(h1) == 64

    checked = check_property(
        generator, assert_deterministic_hash, max_examples=50, seed=seed
    )
    assert checked == 50


def test_invariant_redact_containment() -> None:
    """Verify that redact(secret, show_chars=0) is entirely masked."""
    seed = 1234
    generator = fuzz_strings(seed=seed, count=50, min_length=8, max_length=32)

    def assert_secret_redacted(secret: str) -> None:
        masked = redact(secret, show_chars=0)
        assert isinstance(masked, str)
        assert secret not in masked
        assert "*" in masked

    checked = check_property(
        generator, assert_secret_redacted, max_examples=50, seed=seed
    )
    assert checked == 50


def test_invariant_ttl_cache_capacity_bound() -> None:
    """Verify that ttl_cache never exceeds its configured maxsize."""
    maxsize = 10

    @ttl_cache(ttl=60.0, maxsize=maxsize)
    def compute(key: str) -> int:
        return len(key)

    seed = 5678
    keys = list(fuzz_strings(seed=seed, count=100, min_length=1, max_length=8))

    for key in keys:
        compute(key)
        assert compute.cache_info().size <= maxsize


if __name__ == "__main__":
    test_fuzz_integers_contract()
    test_fuzz_floats_contract()
    test_fuzz_strings_and_bytes_contract()
    test_fuzz_primitives_contract()
    test_fuzz_json_objects_validity()
    test_check_property_success()
    test_check_property_failure_handling()
    test_check_property_exception_handling()
    test_invariant_deep_diff_reflexivity()
    test_invariant_structured_hash_stability()
    test_invariant_redact_containment()
    test_invariant_ttl_cache_capacity_bound()
    print("All property generator tests passed!")
