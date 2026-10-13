"""Perpetual security & concurrency audit - PHASE 5 regression tests.

Each test exposes a concrete numerical-finiteness, input-validation, or
resource-bound defect in the audited modules (typed_config, context,
instrumentation, diagnostics, experiments). Tests are written to FAIL ("red")
against the current source and must pass only after the corresponding
production fix lands. Production code is intentionally not modified.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.diagnostics import exception_dict
from gunz_utils.experiments import (
    compare_numeric_metrics,
    metric_improvement,
    run_variant_matrix,
)


# -----------------------------------------------------------------------------
# experiments.py - int->float overflow crashes metric comparison
# -----------------------------------------------------------------------------


def test_compare_numeric_metrics_handles_huge_int_without_overflow() -> None:
    """Mixed int/float comparison must not raise ``OverflowError``.

    ``compare_numeric_metrics`` falls through to the float branch whenever the
    two operands are not both ``int`` (experiments.py:159). A huge integer
    metric (``>= ~1e308``) mixed with a float then triggers
    ``float(huge_int) -> OverflowError``, so the comparison crashes instead of
    returning a non-finite result. ``run_variant_matrix`` calls
    ``compare_numeric_metrics`` *outside* its per-variant ``try/except``
    (experiments.py:95), so this single metric value aborts the whole matrix.
    """
    for baseline, candidate in (
        ({"m": 10**400}, {"m": 1.5}),
        ({"m": 1.5}, {"m": 10**400}),
    ):
        result = compare_numeric_metrics(baseline, candidate)
        assert result["m"]["numeric"] is True
        assert result["m"]["finite"] is False
        assert math.isfinite(result["m"]["delta"]) is False


def test_run_variant_matrix_does_not_crash_on_huge_int_metric() -> None:
    """A huge-int metric vs a float metric must not abort the whole matrix.

    ``run_variant_matrix`` should report a non-finite comparison rather than
    raising, so one pathological metric cannot take down the entire experiment
    report.
    """
    def setup() -> dict[str, object]:
        return {}

    def run(state, config: dict[str, object]) -> dict[str, object]:
        return {"m": config["m"]}

    matrix = run_variant_matrix(
        setup,
        run,
        {
            "baseline": {"m": 10**400},
            "variant": {"m": 1.5},
        },
    )
    assert "comparisons" in matrix
    assert matrix["comparisons"]["variant"]["m"]["finite"] is False


# -----------------------------------------------------------------------------
# experiments.py - non-finite/boolean improvement threshold accepted silently
# -----------------------------------------------------------------------------


def test_metric_improvement_rejects_non_finite_threshold() -> None:
    """A NaN ``minimum_relative_improvement`` must be rejected, not silently used.

    The only validation is ``minimum_relative_improvement < 0``
    (experiments.py:222-223). Because ``nan < 0`` is ``False``, a NaN threshold
    passes and produces a silently misleading ``supported: False`` result with
    a positive ``relative_improvement``. NaN is not a meaningful threshold and
    must be rejected with ``ValueError`` like any other invalid input.
    """
    matrix = {
        "baseline": "baseline",
        "results": {},
        "comparisons": {
            "variant": {
                "m": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 10.0,
                    "candidate": 5.0,
                },
            },
        },
    }
    with pytest.raises(ValueError):
        metric_improvement(
            matrix,
            variant="variant",
            metric="m",
            minimum_relative_improvement=float("nan"),
        )


def test_metric_improvement_rejects_boolean_threshold() -> None:
    """A bool ``minimum_relative_improvement`` must be rejected.

    ``bool`` is an ``int`` subclass, so ``True < 0`` is ``False`` and a boolean
    threshold slips through validation (experiments.py:222), silently coercing
    ``True`` to ``1.0``. Booleans are not a meaningful improvement threshold
    and should be rejected like every other validated numeric argument in the
    package (e.g. ``parse_bool``/``PolicyUpstream`` reject bools explicitly).
    """
    matrix = {
        "baseline": "baseline",
        "results": {},
        "comparisons": {
            "variant": {
                "m": {
                    "numeric": True,
                    "finite": True,
                    "baseline": 10.0,
                    "candidate": 9.0,
                },
            },
        },
    }
    with pytest.raises(ValueError):
        metric_improvement(
            matrix,
            variant="variant",
            metric="m",
            minimum_relative_improvement=True,
        )


# -----------------------------------------------------------------------------
# diagnostics.py - exception envelope excludes message and redacts context
# -----------------------------------------------------------------------------


def test_exception_dict_redacts_context_and_excludes_message() -> None:
    """``exception_dict`` must never leak raw messages or context secrets.

    Sanity green: raw exception text is excluded by default and the context
    structure is recursively redacted (fully masked at ``show_chars=0``),
    confirming the diagnostics secret-leak protection the audit relies on.
    """
    result = exception_dict(
        ValueError("SECRET-TOKEN"),
        context={
            "password": "hunter2",
            "nested": {"api_key": "abc123"},
        },
    )
    assert result["type"] == "ValueError"
    assert "message" not in result
    assert "SECRET-TOKEN" not in str(result)
    assert "hunter2" not in str(result)
    assert "abc123" not in str(result)
