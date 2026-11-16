"""Tests for Wave 5 Sub-Wave 8: Cache Eviction, TTL & Benchmark Comparisons."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import time

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.benchmark import (
    compare_benchmarks,
    detect_regression,
    generate_markdown_comparison_table,
)
from gunz_utils.cache import (
    FIFOCache,
    LFUCache,
    TTLCache,
    memoize_ttl,
)
from gunz_utils.spec import validate_constraints


def test_fifo_cache():
    cache = FIFOCache(capacity=3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert len(cache) == 3
    assert cache.get("a") == 1
    assert cache.metrics.hits == 1

    #? Insert 4th item, 'a' should be evicted because FIFO preserves insertion order
    cache.put("d", 4)
    assert len(cache) == 3
    assert "a" not in cache
    assert cache.get("a") is None
    assert cache.metrics.misses == 1
    assert cache.metrics.evictions == 1
    assert cache.get("d") == 4
    assert cache["b"] == 2


def test_lfu_cache():
    cache = LFUCache(capacity=3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    #? Access 'a' and 'b' multiple times to increase frequency
    assert cache.get("a") == 1
    assert cache.get("a") == 1
    assert cache.get("b") == 2

    #? 'c' has freq 1, 'b' has 2, 'a' has 3
    #? Putting 'd' should evict 'c'
    cache.put("d", 4)
    assert len(cache) == 3
    assert "c" not in cache
    assert "a" in cache
    assert "b" in cache
    assert "d" in cache
    assert cache.metrics.evictions == 1


def test_ttl_cache():
    cache = TTLCache(capacity=5, ttl_seconds=0.05)
    cache.put("x", 100)
    assert cache.get("x") == 100
    assert cache["x"] == 100

    time.sleep(0.07)
    #? expired
    assert cache.get("x") is None
    assert "x" not in cache
    assert len(cache) == 0


def test_memoize_ttl():
    calls = 0

    @memoize_ttl(ttl_seconds=0.05, maxsize=10)
    def compute(
        x,
    ):
        nonlocal calls
        calls += 1
        return x * 2

    assert compute(5) == 10
    assert compute(5) == 10
    assert calls == 1

    time.sleep(0.06)
    assert compute(5) == 10
    assert calls == 2


def test_benchmark_comparisons():
    assert detect_regression(1.0, 1.10, threshold_pct=5.0)
    assert not detect_regression(1.0, 1.02, threshold_pct=5.0)

    b = {"duration": 1.0, "memory": 100}
    c = {"duration": 1.2, "memory": 90}
    res = compare_benchmarks(b, c, threshold_pct=5.0)
    assert res["regressed"]
    assert res["metrics"]["duration"]["regressed"]
    assert not res["metrics"]["memory"]["regressed"]

    tbl = generate_markdown_comparison_table([
        {
            "name": "test_perf", "baseline": 1.0, "current": 1.2, "delta": 0.2,
            "percent_change": 20.0, "regressed": True,
        }
    ])
    assert "| test_perf | 1.0000 | 1.2000 | +0.2000 | +20.00% | **REGRESSED** |" in tbl


def test_spec_constraints():
    schema = {
        "name": {"type": str, "required": True, "min_len": 2},
        "age": {"type": int, "required": True, "min": 0, "max": 120},
        "role": {"type": str, "allowed": {"admin", "user"}},
    }
    valid = {"name": "Alice", "age": 30, "role": "admin"}
    assert validate_constraints(schema, valid) == []

    invalid = {"name": "A", "age": -5, "role": "superuser"}
    errors = validate_constraints(schema, invalid)
    assert len(errors) == 3
    assert any("length (1) is less than minimum 2" in e for e in errors)
    assert any("is less than minimum 0" in e for e in errors)
    assert any("not in allowed set" in e for e in errors)

    missing = {}
    errs = validate_constraints(schema, missing)
    assert len(errs) == 2
    assert "field 'name' is required" in errs
    assert "field 'age' is required" in errs
