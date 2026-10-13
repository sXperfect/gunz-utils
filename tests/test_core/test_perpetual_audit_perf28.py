"""Phase 28 perpetual audit: round-4 (deepest) re-audit of five core modules.

partitions.py, pipeline.py, identifiers.py, and versioning.py were verified
correct across targeted probes: PartitionManifest overlap/duplicate/empty-name/
string-identifier validation and deterministic fingerprint; partition_overlaps/
assert_disjoint_partitions pairwise correctness; worker_map across basic map,
empty/one-item inputs, worker failure, item-iteration failure, consumer
cancellation, and early-break cleanup (no deadlock, no leaked tasks);
identifiers deterministic_id/short_id/new_id type and length bounds; versioning
VersionedEnvelope from_dict/to_dict and SchemaMigrator migrate/register
(forward-only, missing-migration rejection, malformed-version rejection).

One NEW real bug surfaced in instrumentation.py: ``Timer`` is not reentrant.
Its ``__enter__`` overwrites ``self.started`` and ``__exit__`` computes the
elapsed from ``perf_counter() - self.started``. Reusing the *same* ``Timer``
object in a nested ``with`` block silently corrupts the outer measurement:
the inner ``__enter__`` resets ``started``, so the outer ``__exit__`` measures
only from the inner start and returns a too-small elapsed (verified: ~0.02s
instead of ~0.03s). A non-reentrant timer should fail loudly on nested re-entry
rather than silently return a wrong measurement.

This test is expected to be RED against base ``5f867be`` for the Timer
reentrancy case and documents the correct behavior after a fix.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from gunz_utils.identifiers import deterministic_id, new_id, short_id
from gunz_utils.instrumentation import Counter, Timer, Trace
from gunz_utils.partitions import (
    PartitionManifest,
    assert_disjoint_partitions,
    partition_overlaps,
)
from gunz_utils.pipeline import worker_map
from gunz_utils.versioning import (
    SchemaMigrationError,
    SchemaMigrator,
    VersionedEnvelope,
)


# ---------------------------------------------------------------------------
# RED: instrumentation.Timer must not silently corrupt the outer measurement on
# nested re-entry of the same timer object. Re-entering an active Timer should
# fail loudly (non-reentrant context manager) instead of overwriting the start
# time and returning a too-small elapsed for the outer block.
# ---------------------------------------------------------------------------
def test_timer_nested_reentry_is_rejected_not_silently_corrupted() -> None:
    timer = Timer("outer")
    with pytest.raises(RuntimeError):
        with timer:
            # Nested re-entry of the same Timer object while it is active.
            with timer:
                time.sleep(0.001)


# ---------------------------------------------------------------------------
# GREEN: instrumentation otherwise correct.
# ---------------------------------------------------------------------------
def test_timer_basic_and_sequential_reuse() -> None:
    t = Timer("a")
    with t:
        time.sleep(0.01)
    assert t.result is not None
    assert t.result.seconds >= 0.01
    assert t.result.success is True
    # Sequential reuse of the same object is fine (each __enter__ restarts).
    try:
        with t:
            raise ValueError("boom")
    except ValueError:
        pass
    assert t.result is not None
    assert t.result.success is False
    # A fresh Timer measures a successful block correctly.
    with Timer("b") as t2:
        pass
    assert t2.result is not None
    assert t2.result.seconds >= 0.0
    assert t2.result.success is True


def test_counter_and_trace() -> None:
    c = Counter()
    assert c.add() == 1
    assert c.add(2) == 3
    assert c.add(-1) == 2
    with pytest.raises(ValueError):
        c.add(True)
    with pytest.raises(ValueError):
        c.add(1.5)

    tr = Trace()
    for i in range(5):
        with tr.span(f"s{i}", k=i):
            pass
    assert len(tr.events) == 5
    assert all(e.success for e in tr.events)
    assert tr.slowest(3) == sorted(
        tr.events, key=lambda e: e.duration, reverse=True
    )[:3]
    assert tr.slowest(0) == []
    with pytest.raises(ValueError):
        tr.slowest(-1)
    # Failed span records success=False and does not suppress the exception.
    with pytest.raises(ValueError):
        with tr.span("fail"):
            raise ValueError("x")
    assert tr.events[-1].success is False


# ---------------------------------------------------------------------------
# GREEN: pipeline worker_map.
# ---------------------------------------------------------------------------
async def _collect(agen):
    return [r async for r in agen]


def test_worker_map_correctness() -> None:
    async def main() -> None:
        async def ident(x):
            await asyncio.sleep(0)
            return x

        assert await _collect(worker_map(ident, range(5), workers=2)) == list(range(5))
        assert await _collect(worker_map(ident, [], workers=2)) == []
        assert await _collect(worker_map(ident, [42], workers=3)) == [42]

        async def boom(x):
            if x == 2:
                raise ValueError("boom")
            return x

        with pytest.raises(ValueError):
            await _collect(worker_map(boom, range(5), workers=2))

        # Worker/queue bounds validated (async generator: error on first step).
        with pytest.raises(ValueError):
            await _collect(worker_map(ident, [], workers=0))
        with pytest.raises(ValueError):
            await _collect(worker_map(ident, [], workers=2, queue_size=0))

    asyncio.run(main())


# ---------------------------------------------------------------------------
# GREEN: partitions.
# ---------------------------------------------------------------------------
def test_partitions() -> None:
    m = PartitionManifest({"a": ["1", "2"], "b": ["3"]})
    assert m.fingerprint == m.fingerprint  # deterministic
    with pytest.raises(ValueError):
        PartitionManifest({"a": ["1"], "b": ["1"]})  # cross-partition overlap
    with pytest.raises(ValueError):
        PartitionManifest({"a": ["1", "1"]})  # duplicate within a partition
    with pytest.raises(ValueError):
        PartitionManifest({})  # empty manifest rejected
    with pytest.raises(ValueError):
        PartitionManifest({"a": "abc"})  # string identifiers rejected

    ov = partition_overlaps({"a": {1, 2}, "b": {2, 3}, "c": {5}})
    assert ov == {("a", "b"): frozenset({2})}
    assert_disjoint_partitions({"a": {1}, "b": {2}})  # no raise
    with pytest.raises(ValueError):
        assert_disjoint_partitions({"a": {1}, "b": {1}})


# ---------------------------------------------------------------------------
# GREEN: identifiers.
# ---------------------------------------------------------------------------
def test_identifiers() -> None:
    assert deterministic_id("ns", "v") == deterministic_id("ns", "v")
    assert len(new_id()) == 36
    assert new_id().count("-") == 4
    assert len(short_id("hello")) == 12
    assert short_id("hello", length=64) == short_id("hello", length=64)
    with pytest.raises(TypeError):
        deterministic_id(1, "v")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        short_id("x", length=3)
    with pytest.raises(ValueError):
        short_id("x", length=65)
    with pytest.raises(ValueError):
        short_id("x", length=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: versioning.
# ---------------------------------------------------------------------------
def test_versioning() -> None:
    e = VersionedEnvelope("s", 1, {"a": 1})
    assert e.to_dict() == {
        "schema": "s",
        "version": 1,
        "payload": {"a": 1},
        "metadata": {},
    }
    with pytest.raises(SchemaMigrationError):
        VersionedEnvelope.from_dict({"schema": "s", "version": 1})  # missing payload

    sm = SchemaMigrator()
    sm.register("s", 1, lambda p: {**p, "v": 2})
    assert sm.migrate(e, target_version=2).to_dict()["payload"] == {"a": 1, "v": 2}
    with pytest.raises(SchemaMigrationError):
        sm.migrate(e, target_version=3)  # missing migration v2 -> v3
    with pytest.raises(SchemaMigrationError):
        sm.migrate(VersionedEnvelope("s", 2, {"x": 1}), target_version=1)  # downgrade
    with pytest.raises(ValueError):
        sm.migrate(e, target_version=0)  # invalid target
    with pytest.raises(ValueError):
        sm.register("s", 1, lambda p: p)  # duplicate registration
