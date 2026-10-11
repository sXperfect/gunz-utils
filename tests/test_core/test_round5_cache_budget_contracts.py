"""Finite cache invalidation and cooperative budget contract proofs."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.cache import ttl_cache
from gunz_utils.limits import BudgetExceededError, ResourceBudget


@pytest.mark.parametrize("old_fails", [False, True])
def test_multiple_clears_preserve_fresh_cache_and_old_caller_outcome(
    old_fails: bool,
) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0
    results: list[int] = []
    failures: list[BaseException] = []
    failure = RuntimeError("synthetic old producer failure")

    @ttl_cache(ttl=60, maxsize=1)
    def value() -> int:
        nonlocal calls
        calls += 1
        version = calls
        if version == 1:
            started.set()
            if not release.wait(2):
                raise TimeoutError("synthetic producer release expired")
            if old_fails:
                raise failure
        return version

    def old_caller() -> None:
        try:
            results.append(value())
        except BaseException as error:
            failures.append(error)

    thread = threading.Thread(target=old_caller)
    thread.start()
    try:
        assert started.wait(2)
        value.cache_clear()
        assert value() == 2
        value.cache_clear()
        assert value() == 3
    finally:
        release.set()
        thread.join(2)
    assert not thread.is_alive()
    assert results == ([] if old_fails else [1])
    assert failures == ([failure] if old_fails else [])
    assert value() == 3
    info = value.cache_info()
    assert (info.hits, info.misses, info.size, info.maxsize) == (1, 1, 1, 1)
    assert calls == 3


def test_sync_misses_can_compute_independently_without_holding_cache_lock() -> None:
    rendezvous = threading.Barrier(2)
    count_lock = threading.Lock()
    calls = 0

    @ttl_cache(ttl=60)
    def value() -> int:
        nonlocal calls
        with count_lock:
            calls += 1
            version = calls
        rendezvous.wait(timeout=2)
        return version

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(value)
        second = executor.submit(value)
        assert {first.result(timeout=3), second.result(timeout=3)} == {1, 2}
    assert value() in {1, 2}
    info = value.cache_info()
    assert (info.hits, info.misses, info.size) == (1, 2, 1)


def test_deadline_is_checked_after_successful_body_without_interrupting_it() -> None:
    now = [0.0]
    budget = ResourceBudget(timeout=1, clock=lambda: now[0])
    completed: list[str] = []
    with pytest.raises(BudgetExceededError, match="time budget exceeded"):
        with budget.step():
            now[0] = 2.0
            completed.append("body completed")
    assert completed == ["body completed"]
    assert budget.steps_used == 1


def test_body_exception_is_not_replaced_by_expired_deadline() -> None:
    now = [0.0]
    budget = ResourceBudget(timeout=1, clock=lambda: now[0])
    failure = RuntimeError("synthetic body failure")
    with pytest.raises(RuntimeError) as caught:
        with budget.step():
            now[0] = 2.0
            raise failure
    assert caught.value is failure
    assert budget.steps_used == 1
