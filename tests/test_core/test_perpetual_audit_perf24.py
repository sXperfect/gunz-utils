"""Phase 24 perpetual audit: round-3 re-audit of benchmark/{metrics, compare,
cli, io, report, export, process}.

metrics.py, compare.py, cli.py, io.py, report.py, and export.py were re-audited
and are clean after the phase-22 hardening (scaling_efficiency, _finite_non_negative,
and the CLI/JSON serialization paths all validated). process.py, new to this
phase, still leaks ``OverflowError`` from an unguarded ``float()`` conversion in
``profile_command``'s interval validator — the same defect class as the
phase-19/20/21/22 fixes.

This test is expected to be RED against base ``475214b`` and documents the
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

from gunz_utils.benchmark.process import profile_command  # noqa: E402


# ---------------------------------------------------------------------------
# benchmark.process.profile_command leaks OverflowError for a huge-int interval.
#
# The interval validator (process.py:465-471) evaluates
# ``not math.isfinite(float(interval))`` without guarding the ``float()``
# conversion. A positive interval that is finite as an int but not
# float-representable (e.g. ``10**400``) leaks ``OverflowError`` instead of the
# documented ``ValueError`` ("interval must be a finite positive number").
# The interval check runs before any process is launched, so the probe is safe.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("interval", [10**400, -(10**400)])
def test_profile_command_interval_huge_int_raises_valueerror_not_overflow(
    interval: int,
) -> None:
    with pytest.raises(ValueError, match="interval"):
        profile_command(["true"], interval=interval)  # type: ignore[arg-type]
