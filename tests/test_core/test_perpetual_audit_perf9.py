"""Perpetual correctness & performance audit regressions (phase 9).

Each test pins a defect found during the round-9 audit of the deprecated
``gunz_utils.benchmark`` package (backends/compare/export/gate/build/
environment/experiment/artifacts/cli/diagnostics). The tests currently FAIL
against the audited revision (f48c676, which includes the phase-1..8 fixes);
they encode the expected post-fix behavior and should pass once the
implementation is corrected. Production code is intentionally left untouched.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import json
import statistics
import warnings

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================


# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

warnings.simplefilter("ignore", DeprecationWarning)

# E402: these imports must follow the DeprecationWarning suppression above.
from gunz_utils.benchmark.compare import compare_results  # noqa: E402
from gunz_utils.benchmark.diagnostics import analyze_stability  # noqa: E402
from gunz_utils.benchmark.result import (  # noqa: E402
    BenchmarkResult,
    BenchmarkStats,
    SystemInfo,
)

_SYS = SystemInfo("3.12", "Linux", "x86_64", "GenuineIntel", 8)


def _br(samples: list[float]) -> BenchmarkResult:
    """Build a minimal BenchmarkResult from raw timing samples."""
    mean = statistics.fmean(samples)
    stats = BenchmarkStats(
        minimum=min(samples),
        median=statistics.median(samples),
        mean=mean,
        p95=max(samples),
        p99=max(samples),
        maximum=max(samples),
        stddev=statistics.pstdev(samples),
        ops_per_second=0.0 if mean == 0 else 1.0 / mean,
    )
    return BenchmarkResult("r", tuple(samples), stats, 1, len(samples), _SYS)


# ---------------------------------------------------------------------------
# benchmark.diagnostics.analyze_stability: ``relative_range`` is reported as
# 0.0 when the median is zero, hiding a large spread and suppressing the
# "sample range is high" warning.
#
# ``relative_range = 0.0 if median == 0 else (max - min) / median``
# (diagnostics.py). For samples ``[0, 0, 100]`` the median is 0 and the spread
# is 100, but the function reports ``relative_range == 0.0`` (implying no
# spread) and emits no range warning. The zero-median guard avoids a division
# by zero by returning a value that is numerically indistinguishable from "no
# variance", which is wrong: an infinite relative range should be surfaced
# (and flagged as high) rather than masked. Expected: a non-zero median with
# non-zero spread reports a large (effectively infinite) relative_range and a
# "sample range is high" warning.
# ---------------------------------------------------------------------------


def test_analyze_stability_zero_median_still_reports_large_range() -> None:
    report = analyze_stability(_br([0.0, 0.0, 100.0]))
    assert report.relative_range > 0.2
    assert "sample range is high" in report.warnings


# ---------------------------------------------------------------------------
# benchmark.compare / benchmark.cli: a zero-baseline comparison produces
# ``inf`` changes that the in-scope CLI serializes to non-standard JSON.
#
# ``_change`` returns ``float("inf")`` when the baseline is 0 and the
# candidate is positive (compare.py), so ``compare_results`` yields
# ``median_change == inf`` etc. The ``gunz-benchmark compare`` CLI
# (cli.py) serializes the comparison with ``json.dumps(result.__dict__)``,
# which emits a bare ``Infinity`` literal (Python's ``allow_nan`` default) --
# not RFC 8259 JSON. A zero baseline is legitimate (e.g. a benchmark whose
# timed samples are all 0), so the shipped CLI should emit standards-compliant
# JSON rather than an ``Infinity`` token a strict parser rejects. Expected:
# the serialized comparison must not contain a bare ``Infinity`` (the infinite
# change should be represented as ``null`` or otherwise bounded).
# ---------------------------------------------------------------------------


def test_compare_zero_baseline_serializes_to_standard_json() -> None:
    comparison = compare_results(_br([0.0, 0.0]), _br([0.0, 1.0]))
    payload = json.dumps(comparison.__dict__)
    assert "Infinity" not in payload
