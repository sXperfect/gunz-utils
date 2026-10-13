"""Phase 22 perpetual audit: round-3 re-audit of context/deprecation/enums/benchmark.

context.py, deprecation.py, and enums.py are clean (enums was hardened in
phase 16; value-before-name lookup, fuzzy maps, and int-enum bool rejection all
hold). The benchmark module still leaks ``OverflowError`` from unguarded
``float()`` conversions in two validators — the same defect class as the
phase-19/20/21 fixes but in ``benchmark/metrics`` and ``benchmark/compare``.

These tests are expected to be RED against base ``8ee4855`` and document the
correct behavior after a fix.
"""

from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings(
    "ignore",
    message=r".*benchmark is deprecated.*",
    category=DeprecationWarning,
)

from gunz_utils.benchmark.compare import compare_results  # noqa: E402
from gunz_utils.benchmark.metrics import scaling_efficiency  # noqa: E402
from gunz_utils.benchmark.result import (  # noqa: E402
    BenchmarkResult,
    BenchmarkStats,
    SystemInfo,
)


# ---------------------------------------------------------------------------
# benchmark.metrics.scaling_efficiency leaks OverflowError for a huge-int
# duration.
#
# The baseline guard (metrics.py:127) and the per-row guard (metrics.py:142)
# evaluate ``math.isfinite(float(duration))`` without guarding the ``float()``
# conversion. A positive duration that is finite as an int but not
# float-representable (e.g. ``10**400``) leaks ``OverflowError`` instead of the
# documented ``ValueError`` ("workers and durations must be ... equally sized"
# / finite-positive baseline). The function's contract is to reject
# non-finite/non-positive inputs with ``ValueError``.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "durations",
    [
        [10**400, 2.0],  # baseline (index 0) too large
        [1.0, 10**400],  # non-baseline row too large
    ],
)
def test_scaling_efficiency_huge_int_duration_raises_valueerror_not_overflow(
    durations: list[float],
) -> None:
    with pytest.raises(ValueError, match="duration|workers"):
        scaling_efficiency([1, 2], durations)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# benchmark.compare._finite_non_negative leaks OverflowError for a huge-int
# value.
#
# ``_finite_non_negative`` (compare.py:54) evaluates
# ``math.isfinite(float(value))`` unguarded, so a huge-int ``median_threshold``
# or ``p95_threshold`` passed to ``compare_results`` leaks ``OverflowError``
# instead of the documented ``ValueError`` ("...must be a finite non-negative
# number").
# ---------------------------------------------------------------------------
def _result(median: float = 1.0) -> BenchmarkResult:
    stats = BenchmarkStats(
        minimum=0.5,
        median=median,
        mean=1.0,
        p95=1.0,
        p99=1.0,
        maximum=2.0,
        stddev=0.1,
        ops_per_second=100.0,
    )
    system = SystemInfo(
        python="x",
        platform="x",
        machine="x",
        processor="x",
        cpu_count=1,
    )
    return BenchmarkResult(
        name="t",
        samples=(1.0,),
        stats=stats,
        warmup=0,
        iterations=1,
        system=system,
    )


@pytest.mark.parametrize("threshold_name", ["median_threshold", "p95_threshold"])
def test_compare_threshold_huge_int_raises_valueerror_not_overflow(
    threshold_name: str,
) -> None:
    kwargs = {threshold_name: 10**400}
    with pytest.raises(ValueError, match="threshold"):
        compare_results(_result(), _result(1.1), **kwargs)  # type: ignore[arg-type]
