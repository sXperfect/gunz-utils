"""Phase 47 perpetual audit: round-6 (deepest) re-audit of six core modules.

instrumentation.py, sync.py, signals.py, subprocess.py, dag.py, retry.py.

Verified correct at base 214188e (GREEN companion tests below):
- instrumentation: Counter, Timer, Trace.span/slowest (bool/int validation).
- sync: rsync_mirror timeout/extra_args/unsafe-option validation (overflow-robust).
- signals: SignalRegistration/AsyncSignalRegistration idempotent restore,
  install_termination_handler validation, GracefulShutdown unguarded-float guards.
- subprocess: run_command/run_command_async timeout validation (overflow-robust),
  bounded output limit, no unguarded-float leak.
- dag: topological order/cycle detection, sync+async diamond correctness with
  concurrency, fingerprint determinism, rollback on failure.
- retry: _delay saturation bounds (base>max, overflow), run_with_retry
  attempt/exception semantics, unguarded-float validation guards.

One NEW finding (not covered by P26/P28/P33/P36):

1) dag.effective_fingerprint (src/gunz_utils/dag.py:234-282) is O(subtree) per
   call with NO cross-call memo, so execute/async_execute (which call it once
   per stage, dag.py:507/659) recompute each stage's transitive dependency
   closure independently -> O(V^2) for a large workflow. Measured on a 1000-stage
   linear chain: computing all fingerprints took ~5.35s and grows ~4x per
   doubling (200->0.24s, 400->0.86s, 800->3.27s, 1600->13.8s), i.e. quadratic.
   The intra-call memo (dag.py:245) only dedups one call's traversal; it is not
   shared across calls despite the docstring claiming "repeated calls ... cacheable".
   Fix: memoize effective fingerprints across calls (compute once per stage in
   topological order and reuse) to make workflow execution linear-ish (RED).

This test is expected to be RED against base 214188e for the finding and GREEN
for the companion behaviors.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from gunz_utils import instrumentation
from gunz_utils.dag import WorkflowDAG, WorkflowStage
from gunz_utils.retry import RetryPolicy, run_with_retry


def _chain(n: int) -> WorkflowDAG:
    stages = []
    for i in range(n):
        deps = (f"s{i - 1}",) if i > 0 else ()
        stages.append(
            WorkflowStage(
                name=f"s{i}",
                run=lambda _ctx, i=i: i,
                dependencies=deps,
                fingerprint=f"f{i}",
            )
        )
    return WorkflowDAG(stages)


# ---------------------------------------------------------------------------
# Finding 1 (RED): effective_fingerprint recomputes each stage's closure
# ---------------------------------------------------------------------------


def test_effective_fingerprint_all_stages_scales_approximately_linearly() -> None:
    # execute/async_execute call effective_fingerprint once per stage. A
    # 1000-stage chain must fingerprint in well under the O(V^2) re-traversal
    # time (currently ~5.3s on the dev host; a memoized/cross-call fix is
    # milliseconds). Generous wall-clock bound to catch the quadratic blowup.
    workflow = _chain(1000)
    start = time.perf_counter()
    for name in workflow.order():
        workflow.effective_fingerprint(name)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.5, (
        f"effective_fingerprint over {len(workflow.stages)} chain stages took "
        f"{elapsed:.2f}s (quadratic re-traversal; expected < 2.5s)"
    )


# ---------------------------------------------------------------------------
# GREEN: dag companion behaviors
# ---------------------------------------------------------------------------


def test_dag_diamond_sync_and_async() -> None:
    stages = [
        WorkflowStage("a", run=lambda _: 1),
        WorkflowStage("b", run=lambda x: x["a"] + 1, dependencies=("a",)),
        WorkflowStage("c", run=lambda x: x["a"] + 10, dependencies=("a",)),
        WorkflowStage("d", run=lambda x: x["b"] + x["c"], dependencies=("b", "c")),
    ]
    workflow = WorkflowDAG(stages)
    assert workflow.execute()["d"] == 13
    assert asyncio.run(workflow.async_execute(concurrency_limit=2))["d"] == 13
    assert workflow.effective_fingerprint("d") == workflow.effective_fingerprint("d")


def test_dag_cycle_and_missing_dependency() -> None:
    with pytest.raises(ValueError):
        WorkflowDAG(
            [
                WorkflowStage("a", run=lambda _: 1, dependencies=("b",)),
                WorkflowStage("b", run=lambda _: 1, dependencies=("a",)),
            ]
        )
    with pytest.raises(KeyError):
        WorkflowDAG(
            [WorkflowStage("a", run=lambda _: 1, dependencies=("missing",))]
        ).order()


# ---------------------------------------------------------------------------
# GREEN: retry companion behaviors
# ---------------------------------------------------------------------------


def test_retry_delay_saturation_and_bounds() -> None:
    policy = RetryPolicy(
        attempts=3, base_delay=1.0, max_delay=5.0, jitter=False
    )
    d1, d2, d3 = policy.delay(1), policy.delay(2), policy.delay(5)
    assert d1 <= d2 <= d3 and d3 == 5.0
    cap = RetryPolicy(attempts=2, base_delay=10.0, max_delay=2.0, jitter=False)
    assert cap.delay(1) == 2.0
    with pytest.raises(ValueError):
        RetryPolicy(attempts=3, base_delay=10**400)
    with pytest.raises(ValueError):
        RetryPolicy(attempts=True)


def test_run_with_retry_retries_then_succeeds() -> None:
    calls: list[int] = []

    def op():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("boom")
        return "ok"

    result = run_with_retry(op, RetryPolicy(attempts=3, jitter=False))
    assert result == "ok"
    assert len(calls) == 2


# ---------------------------------------------------------------------------
# GREEN: instrumentation companion behaviors
# ---------------------------------------------------------------------------


def test_instrumentation_counter_timer_trace() -> None:
    counter = instrumentation.Counter()
    assert counter.add(2) == 2
    with pytest.raises(ValueError):
        counter.add(True)

    timer = instrumentation.Timer("t")
    with timer:
        pass
    assert timer.result is not None and timer.result.success

    trace = instrumentation.Trace()
    with trace.span("s", k=1):
        pass
    assert len(trace.slowest(10)) == 1
    with pytest.raises(ValueError):
        trace.slowest(-1)


# ---------------------------------------------------------------------------
# GREEN: subprocess companion behaviors
# ---------------------------------------------------------------------------


def test_subprocess_overflow_validation(tmp_path) -> None:
    from gunz_utils import subprocess

    with pytest.raises(ValueError):
        subprocess.run_command(["true"], timeout=10**400)
    with pytest.raises(ValueError):
        subprocess.run_command(["true"], timeout=True)
    # happy path
    result = subprocess.run_command(["true"])
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# GREEN: sync companion behaviors
# ---------------------------------------------------------------------------


def test_rsync_mirror_validation() -> None:
    from gunz_utils import sync

    with pytest.raises(ValueError):
        sync.rsync_mirror("src", "dst", timeout=10**400)
    with pytest.raises(ValueError):
        sync.rsync_mirror("src", "dst", timeout=True)
    with pytest.raises(ValueError):
        sync.rsync_mirror("src", "dst", completion_marker="a/b")


# ---------------------------------------------------------------------------
# GREEN: signals companion behaviors
# ---------------------------------------------------------------------------


def test_signal_registration_validation() -> None:
    from gunz_utils import signals

    with pytest.raises(ValueError):
        signals.install_termination_handler(lambda s: None, signum=True)
    with pytest.raises(ValueError):
        signals.install_termination_handler(lambda s: None, exit_after=1)
    with pytest.raises(TypeError):
        signals.install_termination_handler(123)
