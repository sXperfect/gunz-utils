"""Perpetual security audit phase 34 (round 4, deepest).

Re-audit of ``formatting``, ``instrumentation``, ``identifiers``, ``plugins``,
and ``versioning``.

Findings:

1. ``instrumentation.Timer.__exit__`` records a measurement without checking
   that a matching ``__enter__`` started one (instrumentation.py:80-90).  When
   ``__exit__`` is invoked without a preceding ``__enter__`` -- or invoked a
   second time after a normal context exit -- it computes
   ``time.perf_counter() - self.started`` where ``started`` is ``0.0`` (or the
   previous entry's start), silently producing a bogus, multi-day elapsed
   value with ``success=True``.  ``__enter__`` already guards against
   reentrancy by raising ``RuntimeError`` (instrumentation.py:66-78), but
   ``__exit__`` has no symmetric guard, so misuse yields silently corrupted
   measurements instead of failing loudly.  Correct behavior: ``__exit__``
   must raise ``RuntimeError`` when the timer is not active, mirroring the
   ``__enter__`` guard.

2. ``plugins.discover_plugins`` does not guard the ``entry_points(group=...)``
   enumeration itself (plugins.py:94).  A corrupt or malformed installed
   distribution causes ``entry_points()`` to raise, and that exception
   propagates out of ``discover_plugins``, aborting discovery of every plugin
   in the group.  The module is documented as "Failure-isolated entry-point
   plugin discovery" and isolates per-entry-point load failures, but the
   enumeration failure breaks the whole discovery instead of being surfaced as
   a typed failure / empty result.  Correct behavior: catch and contain
   enumeration failures so a single corrupt package cannot abort the entire
   group discovery.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: Timer records correct durations and guards reentrancy, Counter and
Trace behave correctly, plugins validation/load/sort/error handling hold,
identifiers are deterministic and validated, formatters handle bounds and
pathological inputs, and versioning validation/migration error typing hold.
"""

import pytest

from gunz_utils import (
    formatting,
    identifiers,
    instrumentation,
    plugins,
    versioning,
)

# ---------------------------------------------------------------------------
# Finding 1: Timer.__exit__ records a bogus measurement without an active timer
# ---------------------------------------------------------------------------


def test_timer_exit_without_enter_raises():
    """RED: calling ``__exit__`` without a matching ``__enter__`` must raise
    (it would otherwise silently record a bogus multi-day duration).  Currently
    ``Timer(\"x\").__exit__(None, None, None)`` returns success=True with an
    elapsed of ~perf_counter() (days).
    """
    timer = instrumentation.Timer("orphan")
    with pytest.raises(RuntimeError):
        timer.__exit__(None, None, None)


def test_timer_double_exit_raises():
    """RED: exiting a timer a second time must raise rather than silently
    overwrite the recorded measurement with a fresh (bogus) duration.
    """
    timer = instrumentation.Timer("twice")
    with timer:
        pass
    with pytest.raises(RuntimeError):
        timer.__exit__(None, None, None)


# ---------------------------------------------------------------------------
# Finding 2: discover_plugins does not isolate entry_points() enumeration
# ---------------------------------------------------------------------------


def test_discover_plugins_isolates_enumeration_failure(monkeypatch):
    """RED: when ``entry_points(group=...)`` raises (e.g. corrupt dist-info),
    ``discover_plugins`` must not propagate the raw error -- it should contain
    the failure and return a result.  Currently the RuntimeError propagates.
    """

    def boom(**kwargs):
        raise RuntimeError("dist-info corrupt")

    monkeypatch.setattr(plugins, "entry_points", boom)
    result = plugins.discover_plugins("some.group")
    assert isinstance(result, tuple)


# ---------------------------------------------------------------------------
# GREEN: instrumentation correctness that must not regress
# ---------------------------------------------------------------------------


def test_counter_add_validates_and_increments():
    """GREEN: Counter.add validates amount and returns the new value."""
    counter = instrumentation.Counter()
    assert counter.add(5) == 5
    assert counter.add(2) == 7
    with pytest.raises(ValueError):
        counter.add(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        counter.add("x")  # type: ignore[arg-type]


def test_timer_enter_exit_records_duration():
    """GREEN: a normal context records a non-negative duration and success."""
    timer = instrumentation.Timer("ok")
    with timer:
        pass
    assert timer.result is not None
    assert timer.result.name == "ok"
    assert timer.result.seconds >= 0
    assert timer.result.success is True


def test_timer_reentrancy_guard():
    """GREEN: nested __enter__ on the same Timer raises RuntimeError."""
    timer = instrumentation.Timer("nested")
    with pytest.raises(RuntimeError):
        with timer:
            with timer:
                pass


def test_trace_span_records_success_and_failure():
    """GREEN: Trace.span records success=True on clean exit and success=False
    on an exception, without suppressing the exception.
    """
    trace = instrumentation.Trace()
    with trace.span("a"):
        pass
    with pytest.raises(ValueError):
        with trace.span("b"):
            raise ValueError("boom")
    assert len(trace.events) == 2
    assert trace.events[0].success is True
    assert trace.events[1].success is False


def test_trace_slowest_sorts_and_validates():
    """GREEN: slowest returns the n slowest spans and validates n."""
    trace = instrumentation.Trace()
    with trace.span("slow"):
        pass
    with trace.span("fast"):
        pass
    assert len(trace.slowest(10)) == 2
    with pytest.raises(ValueError):
        trace.slowest(-1)
    with pytest.raises(ValueError):
        trace.slowest(True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: plugins validation that must not regress
# ---------------------------------------------------------------------------


def test_discover_plugins_validates_group_and_instantiate():
    """GREEN: non-empty string group and bool instantiate are enforced."""
    with pytest.raises(ValueError):
        plugins.discover_plugins("")
    with pytest.raises(ValueError):
        plugins.discover_plugins("  ")
    with pytest.raises(ValueError):
        plugins.discover_plugins("g", instantiate="yes")  # type: ignore[arg-type]


def test_discover_plugins_returns_empty_for_unknown_group(monkeypatch):
    """GREEN: an unknown group yields an empty tuple; results are ordered."""

    def fake_entry_points(**kwargs):
        return []

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)
    assert plugins.discover_plugins("nope") == ()


def test_discover_plugins_orders_and_isolates_load_failures(monkeypatch):
    """GREEN: results are deterministic and a failing plugin is a typed failure
    without aborting siblings.
    """
    from importlib.metadata import EntryPoint

    def fake_entry_points(**kwargs):
        return [
            EntryPoint(name="b", value="mod:b", group="g"),
            EntryPoint(name="a", value="mod:a", group="g"),
        ]

    def fake_load(entry_point):
        if entry_point.name == "a":
            raise ImportError("boom")
        return object()

    monkeypatch.setattr(plugins, "entry_points", fake_entry_points)
    monkeypatch.setattr(EntryPoint, "load", fake_load)
    results = plugins.discover_plugins("g")
    assert [r.info.name for r in results] == ["a", "b"]
    assert results[0].ok is False
    assert results[0].error == "ImportError"
    assert results[1].ok is True
    assert results[1].plugin is not None


# ---------------------------------------------------------------------------
# GREEN: identifiers determinism and validation that must not regress
# ---------------------------------------------------------------------------


def test_new_id_is_uuid4_shape():
    """GREEN: new_id returns a 36-char UUID-shaped string."""
    value = identifiers.new_id()
    assert len(value) == 36
    assert value.count("-") == 4
    assert identifiers.new_id() != identifiers.new_id()


def test_deterministic_id_stable_and_validated():
    """GREEN: deterministic_id is stable and rejects non-string inputs."""
    assert identifiers.deterministic_id("ns", "v") == identifiers.deterministic_id(
        "ns", "v"
    )
    assert identifiers.deterministic_id("ns", "v") != identifiers.deterministic_id(
        "ns", "w"
    )
    with pytest.raises(TypeError):
        identifiers.deterministic_id(1, "v")  # type: ignore[arg-type]


def test_short_id_bounds_and_collision_resistance():
    """GREEN: short_id is deterministic, length-bounded, and distinct inputs
    yield distinct short ids at the default length.
    """
    assert identifiers.short_id("abc") == identifiers.short_id("abc")
    assert (
        identifiers.short_id("abc", length=4)
        != identifiers.short_id("abcd", length=4)
    )
    assert len(identifiers.short_id("abc")) == 12
    assert set(identifiers.short_id("abc")) <= set("0123456789abcdef")
    with pytest.raises(ValueError):
        identifiers.short_id("abc", length=3)
    with pytest.raises(ValueError):
        identifiers.short_id("abc", length=65)
    with pytest.raises(TypeError):
        identifiers.short_id(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: formatter correctness and bounds that must not regress
# ---------------------------------------------------------------------------


def test_format_bytes_correctness_and_bounds():
    """GREEN: format_bytes matches documented examples and rejects bad input."""
    assert formatting.format_bytes(0) == "0 B"
    assert formatting.format_bytes(1536) == "1.5 KB"
    assert formatting.format_bytes(1024, binary=True) == "1.0 KiB"
    assert formatting.format_bytes(-1536) == "-1.5 KB"
    with pytest.raises(ValueError):
        formatting.format_bytes(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        formatting.format_bytes(float("inf"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        formatting.format_bytes(1, precision=21)


def test_format_duration_correctness_and_bounds():
    """GREEN: format_duration matches documented examples and rejects bad input."""
    assert formatting.format_duration(0) == "0ms"
    assert formatting.format_duration(0.5) == "500ms"
    assert formatting.format_duration(45.6) == "45.6s"
    assert formatting.format_duration(3661) == "1h 1m 1s"
    assert formatting.format_duration(-0.5) == "-500ms"
    with pytest.raises(ValueError):
        formatting.format_duration(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        formatting.format_duration(float("nan"))  # type: ignore[arg-type]


def test_format_count_correctness_and_bounds():
    """GREEN: format_count matches documented examples and rejects bad input."""
    assert formatting.format_count(0) == "0"
    assert formatting.format_count(999) == "999"
    assert formatting.format_count(1500) == "1.5K"
    assert formatting.format_count(1_234_567) == "1.2M"
    assert formatting.format_count(-1500) == "-1.5K"
    with pytest.raises(ValueError):
        formatting.format_count(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        formatting.format_count(1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: versioning validation and migration error typing that must not regress
# ---------------------------------------------------------------------------


def test_versioned_envelope_validation_and_roundtrip():
    """GREEN: envelope validates schema/version/metadata and round-trips."""
    env = versioning.VersionedEnvelope("orders", 1, {"x": 1}, {"k": "v"})
    rebuilt = versioning.VersionedEnvelope.from_dict(env.to_dict())
    assert rebuilt == env
    with pytest.raises(ValueError):
        versioning.VersionedEnvelope("", 1, None)
    with pytest.raises(ValueError):
        versioning.VersionedEnvelope("s", 0, None)
    with pytest.raises(ValueError):
        versioning.VersionedEnvelope("s", True, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        versioning.VersionedEnvelope("s", 1, None, metadata=[1, 2])  # type: ignore[arg-type]


def test_from_dict_missing_fields_and_bad_version():
    """GREEN: from_dict rejects missing/malformed fields with SchemaMigrationError."""
    with pytest.raises(versioning.SchemaMigrationError):
        versioning.VersionedEnvelope.from_dict({"schema": "s", "payload": 1})
    with pytest.raises(versioning.SchemaMigrationError):
        versioning.VersionedEnvelope.from_dict(
            {"schema": "s", "version": 0, "payload": 1}
        )
    with pytest.raises(versioning.SchemaMigrationError):
        versioning.VersionedEnvelope.from_dict(
            {"schema": "s", "version": 1, "payload": 1, "metadata": []}
        )


def test_schema_migrator_register_and_migrate():
    """GREEN: register rejects duplicates and migrate moves forward correctly."""
    migrator = versioning.SchemaMigrator()
    migrator.register("s", 1, lambda p: {**p, "v": 2})
    with pytest.raises(ValueError):
        migrator.register("s", 1, lambda p: p)
    result = migrator.migrate(versioning.VersionedEnvelope("s", 1, {"v": 1}),
                              target_version=2)
    assert result.version == 2
    assert result.payload == {"v": 2}


def test_schema_migrator_error_typing():
    """GREEN: downgrade, missing migration, and invalid target_version all
    surface as SchemaMigrationError (migration-domain error type).
    """
    migrator = versioning.SchemaMigrator()
    migrator.register("s", 1, lambda p: p)
    env = versioning.VersionedEnvelope("s", 2, {"x": 1})
    with pytest.raises(versioning.SchemaMigrationError):
        migrator.migrate(env, target_version=1)
    with pytest.raises(versioning.SchemaMigrationError):
        migrator.migrate(versioning.VersionedEnvelope("s", 3, {}), target_version=4)
    with pytest.raises(versioning.SchemaMigrationError):
        migrator.migrate(versioning.VersionedEnvelope("s", 1, {}), target_version=0)
    with pytest.raises(versioning.SchemaMigrationError):
        migrator.migrate(versioning.VersionedEnvelope("s", 1, {}), target_version=True)  # type: ignore[arg-type]
