"""Phase 34 perpetual audit: round-4 (deepest) re-audit of five core modules.

formatting.py, instrumentation.py, identifiers.py, plugins.py, versioning.py.

Verified correct at base ce63019 (GREEN companion tests below):
- formatting: format_bytes (SI/IEC, negatives, zero-magnitude sign suppression,
  huge-int/inf/nan ValueError), format_duration (ms/s/composite, negatives),
  format_count (small/large/negative/huge, precision).
- identifiers: short_id length bounds + determinism, deterministic_id, new_id.
- instrumentation: Counter lock/validation, Timer non-reentrancy + sequential
  reuse, Trace.span success/failure recording, Trace.slowest bounds/ordering.
- plugins: discover_plugins validation + empty-group result.
- versioning: VersionedEnvelope, SchemaMigrator register/migrate/errors.

Two NEW findings in instrumentation.py:

1) Trace.span crashes on un-deepcopyable metadata (src/gunz_utils/
   instrumentation.py:158). ``copy.deepcopy(metadata)`` runs BEFORE the try
   block, so if any metadata value cannot be deep-copied (e.g. a
   ``threading.Lock``, a file handle, a module), the span raises ``TypeError``
   at ``__enter__`` -- the instrumented body never runs and no span is
   recorded. Instrumentation must not break the instrumented operation because
   of a metadata copy failure. Expected: the body still runs and a span is
   recorded (metadata degraded safely). Currently raises and records nothing
   (RED).

2) Trace.span accepts a non-string name (src/gunz_utils/instrumentation.py:135
   and TraceEvent.name :115). ``name`` is typed ``str`` but not validated, so
   ``Trace.span(123)`` records a ``TraceEvent`` with an ``int`` name, violating
   the ``str`` type contract (the package validates such arguments elsewhere).
   Expected: non-string name raises TypeError. Currently accepted (RED).

This test is expected to be RED against base ce63019 for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import threading

import pytest

from gunz_utils import formatting as F
from gunz_utils import identifiers as I
from gunz_utils import versioning as V
from gunz_utils.instrumentation import Counter, Timer, Trace
from gunz_utils.plugins import discover_plugins


# ---------------------------------------------------------------------------
# RED: instrumentation Trace.span robustness + type contract.
# ---------------------------------------------------------------------------
def test_trace_span_tolerates_undeepcopyable_metadata() -> None:
    trace = Trace()
    ran = False
    with trace.span("op", lock=threading.Lock()):
        ran = True
    assert ran is True  # the instrumented body still executes
    assert len(trace.events) == 1  # and a span is still recorded


def test_trace_span_rejects_non_string_name() -> None:
    trace = Trace()
    with pytest.raises(TypeError):
        with trace.span(123):  # type: ignore[arg-type]
            pass


# ---------------------------------------------------------------------------
# GREEN: instrumentation.
# ---------------------------------------------------------------------------
def test_instrumentation_counter() -> None:
    counter = Counter()
    assert counter.add(2) == 2
    assert counter.add(3) == 5
    with pytest.raises(ValueError):
        counter.add(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        counter.add(1.5)  # type: ignore[arg-type]


def test_instrumentation_timer() -> None:
    timer = Timer("t")
    with timer:
        pass
    assert timer.result is not None
    assert timer.result.name == "t"
    assert timer.result.success is True
    assert timer.result.seconds >= 0
    # Sequential reuse works; nested re-entry is rejected.
    with timer:
        pass
    with pytest.raises(RuntimeError):
        with timer:
            with timer:  # type: ignore[misc]
                pass


def test_instrumentation_trace_span_and_slowest() -> None:
    trace = Trace()
    with trace.span("a"):
        pass
    try:
        with trace.span("b"):
            raise ValueError("boom")
    except ValueError:
        pass
    assert len(trace.events) == 2
    assert trace.events[1].success is False
    assert len(trace.slowest(1)) == 1
    assert set(e.name for e in trace.slowest(2)) == {"a", "b"}
    # slowest bounds validation.
    with pytest.raises(ValueError):
        trace.slowest(-1)
    with pytest.raises(ValueError):
        trace.slowest(True)  # type: ignore[arg-type]
    assert trace.slowest(0) == []


# ---------------------------------------------------------------------------
# GREEN: formatting.
# ---------------------------------------------------------------------------
def test_formatting_bytes() -> None:
    assert F.format_bytes(0) == "0 B"
    assert F.format_bytes(1) == "1 B"
    assert F.format_bytes(1536) == "1.5 KB"
    assert F.format_bytes(1024, binary=True) == "1.0 KiB"
    assert F.format_bytes(1_000_000) == "1.0 MB"
    assert F.format_bytes(-1536) == "-1.5 KB"
    assert F.format_bytes(0.4) == "0 B"
    assert F.format_bytes(-0.4) == "0 B"
    with pytest.raises(ValueError):
        F.format_bytes(10**400)
    with pytest.raises(ValueError):
        F.format_bytes(float("inf"))
    with pytest.raises(ValueError):
        F.format_bytes(True)  # type: ignore[arg-type]


def test_formatting_duration() -> None:
    assert F.format_duration(0.5) == "500ms"
    assert F.format_duration(59.9) == "59.9s"
    assert F.format_duration(60) == "1m 0s"
    assert F.format_duration(3661) == "1h 1m 1s"
    assert F.format_duration(90000) == "1d 1h 0m 0s"
    assert F.format_duration(-0.5) == "-500ms"
    with pytest.raises(ValueError):
        F.format_duration(float("nan"))


def test_formatting_count() -> None:
    assert F.format_count(0) == "0"
    assert F.format_count(999) == "999"
    assert F.format_count(1500) == "1.5K"
    assert F.format_count(1_234_567) == "1.2M"
    assert F.format_count(-2500) == "-2.5K"
    assert F.format_count(10**400).endswith("T")
    with pytest.raises(ValueError):
        F.format_count(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        F.format_count(1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: identifiers.
# ---------------------------------------------------------------------------
def test_identifiers() -> None:
    assert len(I.new_id()) == 36
    assert I.deterministic_id("ns", "v") == I.deterministic_id("ns", "v")
    assert I.short_id("abc") == I.short_id("abc")
    assert len(I.short_id("abc")) == 12
    with pytest.raises(ValueError):
        I.short_id("abc", length=3)
    with pytest.raises(ValueError):
        I.short_id("abc", length=65)
    with pytest.raises(ValueError):
        I.short_id("abc", length=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: versioning.
# ---------------------------------------------------------------------------
def test_versioning_envelope() -> None:
    envelope = V.VersionedEnvelope("s", 1, {"a": 1})
    assert envelope.to_dict()["version"] == 1
    restored = V.VersionedEnvelope.from_dict(envelope.to_dict())
    assert restored == envelope
    with pytest.raises(V.SchemaMigrationError):
        V.VersionedEnvelope.from_dict({"schema": "s", "version": 0, "payload": {}})
    with pytest.raises(ValueError):
        V.VersionedEnvelope("s", True, {})  # type: ignore[arg-type]


def test_versioning_migrator() -> None:
    migrator = V.SchemaMigrator()
    migrator.register("s", 1, lambda p: {**p, "migrated": True})
    envelope = V.VersionedEnvelope("s", 1, {})
    migrated = migrator.migrate(envelope, target_version=2)
    assert migrated.version == 2
    assert migrated.payload["migrated"] is True
    with pytest.raises(V.SchemaMigrationError):
        migrator.migrate(envelope, target_version=3)  # missing 2->3
    with pytest.raises(V.SchemaMigrationError):
        migrator.migrate(envelope, target_version=0)
    with pytest.raises(V.SchemaMigrationError):
        migrator.migrate(envelope, target_version=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: plugins.
# ---------------------------------------------------------------------------
def test_plugins_discovery_validation() -> None:
    assert discover_plugins("nonexistent.group.xyz") == ()
    with pytest.raises(ValueError):
        discover_plugins("")
    with pytest.raises(ValueError):
        discover_plugins("group", instantiate=1)  # type: ignore[arg-type]
