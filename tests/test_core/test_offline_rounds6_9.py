"""Finite offline proofs for deep structures, result invariants and cleanup."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
from typing import Any

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.result import Result
from gunz_utils.signals import GracefulShutdown
from gunz_utils.structures import DeepDifference, deep_diff, freeze_structure


def test_deep_diff_handles_acyclic_depth_without_python_recursion() -> None:
    left: Any = 0
    right: Any = 1
    for _ in range(1500):
        left, right = [left], [right]
    assert deep_diff(left, right) == [DeepDifference("[0]" * 1500, "value", 0, 1)]


def test_freeze_handles_acyclic_depth_without_python_recursion() -> None:
    value: Any = 7
    for _ in range(1500):
        value = [value]
    frozen = freeze_structure(value)
    for _ in range(1500):
        assert isinstance(frozen, tuple) and len(frozen) == 1
        frozen = frozen[0]
    assert frozen == 7


def test_freeze_rejects_cycles_and_copies_shared_subtrees() -> None:
    cycle: list[Any] = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="cycle"):
        freeze_structure(cycle)
    shared = [1]
    frozen = freeze_structure([shared, shared])
    shared.append(2)
    assert frozen == ((1,), (1,))


def test_deep_diff_preserves_value_order_and_ignores_alias_topology() -> None:
    shared = [1]
    assert deep_diff([shared, shared], [[1], [1]]) == []
    differences = deep_diff({"b": [1, 2], "a": 1}, {"b": [9], "c": 3})
    assert [(d.path, d.kind) for d in differences] == [
        ("a", "missing_right"),
        ("b", "length"),
        ("b[0]", "value"),
        ("b[1]", "missing_right"),
        ("c", "missing_left"),
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"value": 1, "error": "synthetic", "_ok": True},
        {"value": 1, "error": "synthetic", "_ok": False},
        {"value": 1, "_ok": False},
        {"error": "synthetic", "_ok": True},
        {"_ok": 1},
    ],
)
def test_result_constructor_rejects_inconsistent_variant(
    kwargs: dict[str, Any],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        Result(**kwargs)


def test_result_none_payloads_remain_valid() -> None:
    assert Result.ok(None).is_ok and Result.ok(None).unwrap() is None
    assert Result.err(None).is_err and Result.err(None).unwrap_or(7) == 7
    assert Result().is_ok


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), -float("inf")])
def test_cleanup_rejects_nonfinite_timeout(
    timeout: float,
) -> None:
    with pytest.raises(ValueError):
        GracefulShutdown(timeout=timeout)


def test_cleanup_propagates_direct_task_cancellation() -> None:
    async def proof() -> None:
        cleanup = GracefulShutdown(timeout=1)
        started = asyncio.Event()
        released = asyncio.Event()

        async def callback() -> None:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                released.set()

        cleanup.add_callback(callback)
        task = asyncio.create_task(cleanup.run_cleanup())
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert released.is_set() and task.cancelled()

    asyncio.run(proof())


def test_cleanup_keeps_ordinary_errors_and_lifo_order() -> None:
    calls: list[int] = []
    failure = RuntimeError("synthetic cleanup failure")

    def first() -> None:
        calls.append(1)

    def second() -> None:
        calls.append(2)
        raise failure

    cleanup = GracefulShutdown()
    cleanup.add_callback(first)
    cleanup.add_callback(second)
    errors = asyncio.run(cleanup.run_cleanup())
    assert calls == [2, 1]
    assert errors == [(second, failure)]


def test_freeze_mapping_keys_follow_defensive_copy_semantics() -> None:
    key = object()
    frozen = freeze_structure({key: [1]})
    copied_key = next(iter(frozen))
    assert copied_key is not key and key not in frozen
    assert frozen[copied_key] == (1,)
    with pytest.raises(TypeError):
        frozen[copied_key] = (2,)


def test_async_predicate_timeout_is_cooperative_and_outer_cancel_drains() -> None:
    from gunz_utils.testing import eventually_async

    async def proof() -> None:
        completed = asyncio.Event()

        async def predicate() -> bool:
            try:
                await asyncio.Event().wait()
                return False
            finally:
                completed.set()

        with pytest.raises(TimeoutError):
            await asyncio.wait_for(eventually_async(predicate, timeout=0.001), 0.03)
        assert completed.is_set()

    asyncio.run(proof())


def test_plugin_fatal_exception_policy_is_preserved(
    monkeypatch: Any,
) -> None:
    import gunz_utils.plugins as plugins

    class Entry:
        name = "synthetic"
        value = "synthetic:plugin"

        def load(self) -> Any:
            raise SystemExit(7)

    monkeypatch.setattr(plugins, "entry_points", lambda **kwargs: [Entry()])
    with pytest.raises(SystemExit) as caught:
        plugins.discover_plugins("synthetic")
    assert caught.value.code == 7


def test_empty_operation_id_generates_and_restores_outer_context() -> None:
    from gunz_utils.context import correlation_id, operation_context

    with operation_context("outer"):
        with operation_context("") as generated:
            assert generated and generated != "outer"
            assert correlation_id() == generated
        assert correlation_id() == "outer"


def test_stop_before_start_can_start_and_stop_normally() -> None:
    from unittest.mock import patch

    from gunz_utils.timing import Timer

    with patch("gunz_utils.timing.time.perf_counter", side_effect=[5.0, 10.0, 12.0]):
        timer = Timer(auto_start=False)
        timer.stop()
        assert timer.elapsed == 0
        timer.start()
        timer.stop()
        assert timer.elapsed == 2


def test_explicit_string_flattening_fails_boundedly_without_changing_default() -> None:
    from gunz_utils.iteration import flatten

    assert list(flatten(["a"])) == ["a"]
    with pytest.raises(ValueError, match="cycle|nesting"):
        list(flatten(["a"], types=(list, tuple, str), max_nesting=10))


def test_deep_diff_does_not_eagerly_read_later_sequence_items() -> None:
    from collections.abc import Sequence

    class BadEquality:
        def __eq__(self,
            other: object,
        ) -> bool:
            raise RuntimeError("synthetic equality failure")

    class Guarded(Sequence[Any]):
        def __init__(self) -> None:
            self.reads: list[int] = []

        def __len__(self) -> int:
            return 100000

        def __getitem__(self,
            index: Any,
        ) -> Any:
            self.reads.append(index)
            if index != 0:
                raise AssertionError("later item read before first equality")
            return BadEquality()

    left, right = Guarded(), Guarded()
    with pytest.raises(TypeError, match="leaf equality failed"):
        deep_diff(left, right)
    assert left.reads == right.reads == [0]


def test_freeze_empty_siblings_preserves_previous_outputs() -> None:
    frozen = freeze_structure([1, [], {}, set(), 2])
    assert frozen == (1, (), {}, frozenset(), 2)


@pytest.mark.parametrize("limit", [-1, True, 1.5])
def test_retention_limit_rejects_before_consuming_input(
    limit: Any,
) -> None:
    from gunz_utils.structures import retain_priority_and_recent
    consumed: list[int] = []
    def items() -> Any:
        consumed.append(1)
        yield 1
    with pytest.raises(ValueError, match="max_recent"):
        retain_priority_and_recent(
            items(), is_priority=lambda value: False, max_recent=limit
        )
    assert consumed == []
