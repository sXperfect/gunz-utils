"""Tests for lightweight structured tracing."""

from __future__ import annotations

import pytest

from gunz_utils.instrumentation import Trace


def test_trace_records_successful_span_metadata() -> None:
    trace = Trace()

    with trace.span("load", source="cache"):
        pass

    assert len(trace.events) == 1
    event = trace.events[0]
    assert event.name == "load"
    assert event.metadata == {"source": "cache"}
    assert event.success
    assert event.duration >= 0.0


def test_trace_records_failed_span_without_suppressing_exception() -> None:
    trace = Trace()

    with pytest.raises(RuntimeError, match="boom"):
        with trace.span("work"):
            raise RuntimeError("boom")

    assert len(trace.events) == 1
    assert not trace.events[0].success


def test_trace_slowest_orders_descending_and_respects_limit() -> None:
    trace = Trace()
    with trace.span("first"):
        pass
    with trace.span("second"):
        sum(range(1000))

    result = trace.slowest(1)

    assert len(result) == 1
    assert result[0].duration == max(event.duration for event in trace.events)


def test_trace_slowest_rejects_negative_limit() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        Trace().slowest(-1)


def test_trace_snapshots_nested_metadata_at_span_entry() -> None:
    trace = Trace()
    metadata = {
        "nested": {
            "value": 1,
        }
    }

    with trace.span(
        "work",
        payload=metadata,
    ):
        metadata["nested"]["value"] = 2

    assert trace.events[0].metadata["payload"]["nested"]["value"] == 1
