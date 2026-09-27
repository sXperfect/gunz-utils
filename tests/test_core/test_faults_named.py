"""Tests for deterministic fault-injection helpers."""

from __future__ import annotations

import pytest

import gunz_utils
from gunz_utils.faults import (
    FailAfter,
    FaultSequence,
    InjectedFault,
    NamedFaultInjector,
)


def test_named_fault_injector_only_fails_selected_checkpoint() -> None:
    injector = NamedFaultInjector(
        frozenset({"after_write"}),
    )

    injector.checkpoint("before_write")

    with pytest.raises(InjectedFault, match="after_write"):
        injector.checkpoint("after_write")


def test_named_fault_injector_supports_custom_exception_factory() -> None:
    injector = NamedFaultInjector(
        frozenset({"commit"}),
        exception_factory=lambda name: ValueError(
            f"custom {name}"
        ),
    )

    with pytest.raises(ValueError, match="custom commit"):
        injector.checkpoint("commit")


def test_package_root_preserves_historical_foundation_exports() -> None:
    assert gunz_utils.FailAfter is not None
    assert gunz_utils.FaultSequence is not None
    assert callable(gunz_utils.correlation_id)
    assert callable(gunz_utils.ensure_correlation_id)
    assert callable(gunz_utils.operation_context)
    assert gunz_utils.GunzDeprecationWarning is not None
    assert callable(gunz_utils.deprecated)


def test_new_fault_api_is_namespace_first() -> None:
    import gunz_utils.faults as faults

    assert faults.NamedFaultInjector is NamedFaultInjector
    assert faults.InjectedFault is InjectedFault


def test_named_fault_injector_freezes_input_collection() -> None:
    names = {"first"}
    injector = NamedFaultInjector(names)

    names.add("second")

    with pytest.raises(InjectedFault):
        injector.checkpoint("first")
    injector.checkpoint("second")


def test_named_fault_injector_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        NamedFaultInjector(frozenset({""}))

    with pytest.raises(TypeError, match="callable"):
        NamedFaultInjector(
            frozenset({"x"}),
            exception_factory=object(),
        )



def test_fail_after_enforces_success_budget() -> None:
    fault = FailAfter(
        successes=2,
        exception_factory=lambda: RuntimeError("expected"),
    )

    fault()
    fault()
    with pytest.raises(RuntimeError, match="expected"):
        fault()

    assert fault.calls == 3


@pytest.mark.parametrize(
    "successes",
    [-1, True, 1.5],
)
def test_fail_after_rejects_invalid_success_budget(
    successes: object,
) -> None:
    with pytest.raises(ValueError, match="successes"):
        FailAfter(
            successes=successes,
            exception_factory=lambda: RuntimeError(),
        )


def test_fail_after_requires_exception_factory_result() -> None:
    fault = FailAfter(
        successes=0,
        exception_factory=lambda: "not-an-exception",
    )

    with pytest.raises(TypeError, match="BaseException"):
        fault()


def test_fault_sequence_freezes_indices_and_uses_one_based_calls() -> None:
    failures = {2}
    sequence = FaultSequence(failures)
    failures.add(1)

    sequence.check(lambda: RuntimeError("expected"))
    with pytest.raises(RuntimeError, match="expected"):
        sequence.check(lambda: RuntimeError("expected"))

    assert sequence.failures == frozenset({2})
    assert sequence.calls == 2


@pytest.mark.parametrize(
    "failures",
    [
        {0},
        {-1},
        {True},
        {1.5},
    ],
)
def test_fault_sequence_rejects_invalid_failure_indices(
    failures: object,
) -> None:
    with pytest.raises(ValueError, match="positive one-based"):
        FaultSequence(failures)


def test_fault_sequence_validates_exception_factory() -> None:
    sequence = FaultSequence({1})

    with pytest.raises(TypeError, match="callable"):
        sequence.check(object())

    bad_result = FaultSequence({1})
    with pytest.raises(TypeError, match="BaseException"):
        bad_result.check(lambda: "not-an-exception")


def test_named_fault_injector_validates_checkpoint_and_factory_result() -> None:
    injector = NamedFaultInjector(
        {"x"},
        exception_factory=lambda _name: "not-an-exception",
    )

    with pytest.raises(ValueError, match="must not be empty"):
        injector.checkpoint("")

    with pytest.raises(TypeError, match="BaseException"):
        injector.checkpoint("x")
