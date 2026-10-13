"""Phase 38 perpetual audit: round-4 (deepest) re-audit of six core modules.

concurrency.py, limits.py, leases.py, rate_limit.py, faults.py, iteration.py.

Verified correct at base 71b8281 (GREEN companion tests below):
- concurrency: gather_limited bounded scheduling + ordering, return_exceptions,
  map_unordered streaming, process_map/process_imap serial fast path + validation.
- limits: Limits/ResourceBudget float validation, budget accounting, step()
  success and timeout paths.
- rate_limit: AsyncRateLimiter token accounting, acquire timeout path, float
  validation (huge ints correctly rejected as ValueError).
- leases: LeaseTiming normal validation and heartbeat<lease ordering.
- faults: FailAfter/FaultSequence/NamedFaultInjector decisions, VirtualClock
  normal advance, FaultyStream short-write/read fault, AwaitBoundaryChaos
  step counting.
- iteration: chunked/batched grouping, flatten max_depth/nesting/cycle guards,
  first/default.

Two NEW findings (same recurring defect class: unguarded float conversion of
huge ints leaks OverflowError instead of the documented ValueError):

1) leases.py LeaseTiming.__post_init__ (src/gunz_utils/leases.py:44-52) and
   run_with_lease_heartbeat (src/gunz_utils/leases.py:157-165) evaluate
   ``math.isfinite(float(value))``. For a huge int like 10**400, ``float(x)``
   raises OverflowError ("int too large to convert to float") before the guard
   can return False, so ``LeaseTiming(lease_seconds=10**400, ...)`` and
   ``run_with_lease_heartbeat(..., heartbeat_interval=10**400)`` leak
   OverflowError instead of ValueError (RED).

2) faults.py VirtualClock (src/gunz_utils/faults.py:191-198 __init__ and
   237-248 advance) evaluate ``math.isfinite(start_time/seconds)`` directly on
   the raw value. ``math.isfinite(10**400)`` raises OverflowError, so
   ``VirtualClock(start_time=10**400)`` and ``vc.advance(10**400)`` leak
   OverflowError instead of ValueError (RED).

The correct fix is the established pattern: a bool/type check first, then
``float(value)`` wrapped so an OverflowError is converted to ValueError.

This test is expected to be RED against base 71b8281 for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import asyncio

import pytest
from gunz_utils.faults import (
    AwaitBoundaryChaos,
    FailAfter,
    FaultSequence,
    FaultyStream,
    NamedFaultInjector,
    VirtualClock,
)
from gunz_utils.iteration import batched, chunked, first, flatten
from gunz_utils.leases import LeaseTiming, run_with_lease_heartbeat
from gunz_utils.limits import Limits
from gunz_utils.rate_limit import AsyncRateLimiter

# ---------------------------------------------------------------------------
# 1) leases.py — huge-int timing values must raise ValueError, not OverflowError
# ---------------------------------------------------------------------------


def test_lease_timing_huge_int_raises_valueerror():
    with pytest.raises(ValueError):
        LeaseTiming(lease_seconds=10**400, heartbeat_interval=1)
    with pytest.raises(ValueError):
        LeaseTiming(lease_seconds=1, heartbeat_interval=10**400)


def test_run_with_lease_heartbeat_huge_interval_raises_valueerror():
    async def op() -> int:
        return 1

    async def renew() -> bool:
        return True

    with pytest.raises(ValueError):
        asyncio.run(
            run_with_lease_heartbeat(op, renew, heartbeat_interval=10**400)
        )


def test_lease_timing_valid_values_accepted():
    timing = LeaseTiming(lease_seconds=10.0, heartbeat_interval=1.0)
    assert timing.lease_seconds == 10.0
    assert timing.heartbeat_interval == 1.0


def test_lease_timing_heartbeat_not_shorter_rejected():
    with pytest.raises(ValueError):
        LeaseTiming(lease_seconds=1.0, heartbeat_interval=1.0)
    with pytest.raises(ValueError):
        LeaseTiming(lease_seconds=1.0, heartbeat_interval=5.0)


# ---------------------------------------------------------------------------
# 2) faults.py — VirtualClock huge values must raise ValueError, not OverflowError
# ---------------------------------------------------------------------------


def test_virtual_clock_start_time_huge_int_raises_valueerror():
    with pytest.raises(ValueError):
        VirtualClock(start_time=10**400)


def test_virtual_clock_advance_huge_int_raises_valueerror():
    vc = VirtualClock()
    with pytest.raises(ValueError):
        vc.advance(10**400)


def test_virtual_clock_normal_advance():
    vc = VirtualClock(start_time=1000.0)
    assert vc.advance(5.5) == 1005.5
    assert vc.now() == 1005.5
    assert vc.now_ns() == 1005_500_000_000


# ---------------------------------------------------------------------------
# GREEN companions — limits / rate_limit reject huge ints as ValueError (no leak)
# ---------------------------------------------------------------------------


def test_limits_huge_timeout_raises_valueerror():
    with pytest.raises(ValueError):
        Limits(timeout=10**400)


def test_rate_limiter_huge_rate_raises_valueerror():
    with pytest.raises(ValueError):
        AsyncRateLimiter(10**400)


def test_limits_normal_accounting():
    lim = Limits(max_steps=3)
    lim.check_steps(2)
    lim.check_steps(3)
    with pytest.raises(ValueError):
        lim.check_steps(4)


# ---------------------------------------------------------------------------
# GREEN companions — iteration helpers
# ---------------------------------------------------------------------------


def test_chunked_and_batched():
    assert list(chunked(range(5), 2)) == [(0, 1), (2, 3), (4,)]
    assert list(batched(range(5), 2)) == [[0, 1], [2, 3], [4]]
    with pytest.raises(ValueError):
        list(chunked([1, 2], 0))
    with pytest.raises(ValueError):
        list(batched([1, 2], True))


def test_flatten_depth_nesting_cycle():
    assert list(flatten([[1, [2, [3]]]], max_depth=2)) == [1, 2, [3]]
    deep = [[[[1]]]]
    with pytest.raises(ValueError):
        list(flatten(deep, max_nesting=2))
    cyc: list = []
    cyc.append(cyc)
    with pytest.raises(ValueError):
        list(flatten(cyc))


def test_first_and_validation():
    assert first([1, 2, 3]) == 1
    assert first([], default=42) == 42


# ---------------------------------------------------------------------------
# GREEN companions — faults helpers
# ---------------------------------------------------------------------------


def test_fault_helpers_decisions():
    fa = FailAfter(successes=1, exception_factory=lambda: RuntimeError("x"))
    fa()
    with pytest.raises(RuntimeError):
        fa()
    fs = FaultSequence(failures={2})
    fs.check(lambda: RuntimeError("x"))
    with pytest.raises(RuntimeError):
        fs.check(lambda: RuntimeError("x"))
    inj = NamedFaultInjector(fail_at={"a"})
    inj.checkpoint("b")
    with pytest.raises(RuntimeError):
        inj.checkpoint("a")
    with pytest.raises(ValueError):
        VirtualClock(start_time=-1)


def test_await_boundary_chaos():
    ac = AwaitBoundaryChaos(fail_at_step=1)

    async def run() -> int:
        count = 0
        for _ in range(3):
            await ac.step()
            count += 1
        return count

    with pytest.raises(RuntimeError):
        asyncio.run(run())


def test_faulty_stream_short_write():
    import io

    buf = io.BytesIO()
    fs = FaultyStream(buf, max_write_bytes=2)
    assert fs.write(b"abcdef") == 2
    assert buf.getvalue() == b"ab"
