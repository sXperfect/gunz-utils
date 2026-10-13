"""Perpetual security audit phase 39 (round 4, deepest).

Re-audit of ``formatting``, ``hashing``, ``identifiers``, ``time_utils``,
``timing``, and ``stats``.

Result: NO genuine NEW security defect found in this round. The recurring
unguarded-float ``OverflowError -> ValueError`` pattern is handled on every
conversion path (``formatting._finite_float``,
``time_utils.monotonic_deadline``/``remaining``,
``stats._finite_values``/``confidence``/``confidence_z``); integer/bool
boundaries, timezone/monotonic-clock usage, hash/identifier determinism and
strength, and exception-safety are all sound. This file pins that correct
behavior so future changes cannot regress it. It contains no RED tests because
there is no genuine defect to expose; per the phase policy, modules that are
already correct are reported as such rather than padded with weak findings.

Coverage:
- formatting: finite-only inputs (bool/nan/inf/huge-int rejected), negative
  sign preservation and zero suppression, SI/IEC scaling, count formatting
  through the tera scale, composite duration rendering.
- hashing: algo allowlist, digest-length cap on short_hash, streaming file
  hashing, canonical structured hashing.
- identifiers: length bounds on short_id, deterministic uuid5, uuid4.
- time_utils: huge-int timeout/deadline -> ValueError (no OverflowError leak),
  monotonic deadlines, non-negative remaining.
- timing: monotonic perf_counter, idempotent stop, context-manager stop.
- stats: finite-only observations, confidence/confidence_z bounds, seed
  determinism, non-finite interval -> OverflowError, mismatched-length pairs
  rejected, overflow-robust mean.
"""

import math

import pytest

from gunz_utils.formatting import format_bytes, format_count, format_duration
from gunz_utils.hashing import (
    content_hash,
    file_hash,
    short_hash,
    structured_hash,
)
from gunz_utils.identifiers import deterministic_id, new_id, short_id
from gunz_utils.stats import (
    bootstrap_mean_ci,
    normal_mean_summary,
    paired_effect,
)
from gunz_utils.time_utils import expired, monotonic_deadline, remaining
from gunz_utils.timing import Timer, timer


def test_format_bytes_rejects_non_finite_and_bool() -> None:
    with pytest.raises(ValueError):
        format_bytes(float("nan"))
    with pytest.raises(ValueError):
        format_bytes(float("inf"))
    with pytest.raises(ValueError):
        format_bytes(True)
    with pytest.raises(ValueError):
        format_bytes(10**400)  # huge int -> OverflowError must surface as ValueError
    with pytest.raises(ValueError):
        format_bytes(1.0, precision=100)  # precision out of 0..20


def test_format_bytes_scaling_and_sign() -> None:
    assert format_bytes(0) == "0 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(1024, binary=True) == "1.0 KiB"
    assert format_bytes(-1500) == "-1.5 KB"
    assert format_bytes(-0.5) == "0 B"  # negative fractional magnitude -> 0 B
    assert format_bytes(1e12, binary=False).endswith("TB")


def test_format_duration_branches() -> None:
    assert format_duration(0) == "0ms"
    assert format_duration(0.5) == "500ms"
    assert format_duration(-0.0001) == "0ms"  # sign suppressed on zero magnitude
    assert format_duration(45.6) == "45.6s"
    assert format_duration(90.4) == "1m 30s"
    assert format_duration(3661) == "1h 1m 1s"
    assert format_duration(86400) == "1d 0h 0m 0s"
    with pytest.raises(ValueError):
        format_duration(float("inf"))


def test_format_count_through_tera_and_sign() -> None:
    assert format_count(999) == "999"
    assert format_count(1500) == "1.5K"
    assert format_count(-1500) == "-1.5K"
    assert format_count(1_234_567) == "1.2M"
    assert format_count(10**30).endswith("T")
    with pytest.raises(ValueError):
        format_count(1.5)
    with pytest.raises(ValueError):
        format_count(True)


def test_hashing_algo_allowlist_and_type_checks() -> None:
    assert content_hash(b"hello") == content_hash("hello")
    with pytest.raises(ValueError):
        content_hash(b"x", algo="not-real")
    with pytest.raises(TypeError):
        content_hash(bytearray(b"x"))
    assert content_hash(b"x", algo="sha256")


def test_short_hash_respects_digest_length() -> None:
    assert len(short_hash(b"x", chars=64)) == 64
    with pytest.raises(ValueError):
        short_hash(b"x", chars=128, algo="sha256")  # exceeds 64-char digest
    with pytest.raises(ValueError):
        short_hash(b"x", chars=2)  # below min


def test_structured_hash_deterministic_across_key_order() -> None:
    assert structured_hash({"a": 1, "b": 2}) == structured_hash({"b": 2, "a": 1})


def test_file_hash_streams(tmp_path) -> None:
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello world" * 1000)
    assert file_hash(str(p)) == content_hash(b"hello world" * 1000)
    with pytest.raises(ValueError):
        file_hash(str(p), chunk_size=0)


def test_identifiers_bounds_and_determinism() -> None:
    assert new_id()
    assert deterministic_id("ns", "v") == deterministic_id("ns", "v")
    assert short_id("x") == short_id("x")
    assert len(short_id("x", length=16)) == 16
    with pytest.raises(ValueError):
        short_id("x", length=3)
    with pytest.raises(ValueError):
        short_id("x", length=128)


def test_time_utils_huge_int_does_not_leak_overflow() -> None:
    with pytest.raises(ValueError):
        monotonic_deadline(10**400)
    with pytest.raises(ValueError):
        remaining(10**400)
    d = monotonic_deadline(5.0)
    assert remaining(d) >= 0.0
    assert expired(d) is False


def test_timer_monotonic_and_idempotent_stop() -> None:
    t = Timer(auto_start=False)
    assert t.elapsed == 0.0
    t.start()
    t.stop()
    first = t.elapsed
    t.stop()  # idempotent
    assert t.elapsed == first
    with timer() as timed:
        pass
    assert timed.elapsed >= 0.0


def test_stats_rejects_non_finite_and_bool_values() -> None:
    with pytest.raises(ValueError):
        bootstrap_mean_ci([1.0, float("nan")])
    with pytest.raises(ValueError):
        bootstrap_mean_ci([1.0, True])
    with pytest.raises(ValueError):
        bootstrap_mean_ci([1.0, 10**400])


def test_stats_confidence_and_z_bounds() -> None:
    with pytest.raises(ValueError):
        bootstrap_mean_ci([1.0, 2.0], confidence=1.0)
    with pytest.raises(ValueError):
        bootstrap_mean_ci([1.0, 2.0], confidence=0.0)
    with pytest.raises(ValueError):
        normal_mean_summary([1.0, 2.0], confidence_z=-1.0)


def test_stats_bootstrap_deterministic_with_seed() -> None:
    a = bootstrap_mean_ci([1.0, 2.0, 3.0, 4.0], samples=100, seed=42)
    b = bootstrap_mean_ci([1.0, 2.0, 3.0, 4.0], samples=100, seed=42)
    assert a.mean == b.mean and a.low == b.low and a.high == b.high


def test_stats_overflow_robust_mean_and_interval() -> None:
    # Normalized mean survives 1e308-scale observations.
    ci = bootstrap_mean_ci([1e308, -1e308, 0.0], samples=50)
    assert math.isfinite(ci.mean)
    # A non-finite normal-mean interval is surfaced as OverflowError.
    with pytest.raises(OverflowError):
        normal_mean_summary([1e308, 1e307], confidence_z=1e308)
    # stdev is overflow-robust and stays finite for finite paired inputs.
    pe = paired_effect([1e308, -1e308], [0.0, 0.0])
    assert math.isfinite(pe.standard_deviation)


def test_stats_paired_effect_validations() -> None:
    with pytest.raises(ValueError):
        paired_effect([1.0, 2.0], [1.0])
    with pytest.raises(ValueError):
        paired_effect([1e308], [-1e308])  # difference overflows float
    # A single finite pair yields mean but no standardized effect.
    single = paired_effect([1.0], [-1.0])
    assert single.observations == 1 and single.standardized_effect is None
    pe = paired_effect([1.0, 2.0, 3.0], [1.0, 1.0, 1.0])
    assert pe.observations == 3
