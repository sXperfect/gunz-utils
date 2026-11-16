"""Regression checks for cleanup, throttling, and numerical fixes."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
from __future__ import annotations

import asyncio
import inspect
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
import gunz_utils.async_utils as async_utils
import gunz_utils.signals as signals
import gunz_utils.subprocess as commands
from gunz_utils.benchmark.environment import capture_noise_info
from gunz_utils.benchmark.metrics import process_metrics
from gunz_utils.leases import LeaseHeartbeat, LeaseLostError
from gunz_utils.math_utils import (
    cosine_similarity,
    dot_product,
    vector_norm,
    vector_normalize,
)


@pytest.mark.parametrize("scale", [1e-300, 1.0, 1e300])
def test_vector_operations_preserve_direction_across_scales(
    scale: float,
) -> None:
    vector = [3 * scale, 4 * scale]
    assert vector_norm(vector) == pytest.approx(5 * scale, rel=1e-14, abs=0)
    assert vector_normalize(vector) == pytest.approx([0.6, 0.8])
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)
    assert cosine_similarity(vector, [-x for x in vector]) == pytest.approx(-1.0)


def test_scaled_general_norm_and_compensated_dot_product() -> None:
    assert vector_norm([1e200, 1e200], p=4) == pytest.approx(2 ** 0.25 * 1e200)
    assert dot_product([1e16, 1.0, -1e16], [1.0] * 3) == 1.0


def test_direction_is_defined_when_the_unscaled_norm_overflows() -> None:
    vector = [1.7e308, 1.7e308]
    expected = 1 / math.sqrt(2)
    assert vector_normalize(vector) == pytest.approx([expected, expected])
    assert cosine_similarity(vector, vector) == pytest.approx(1)


def test_gather_failure_drains_siblings_before_raising() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cleaned = asyncio.Event()

        async def fail() -> int:
            await started.wait()
            raise LookupError("worker failed")

        async def sibling() -> int:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                await asyncio.sleep(0)
                cleaned.set()
            return 1

        with pytest.raises(LookupError, match="worker failed"):
            await async_utils.gather_with_concurrency(2, fail(), sibling())
        assert cleaned.is_set()

    asyncio.run(scenario())


def test_gather_cancellation_closes_unscheduled_coroutines() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cleaned = asyncio.Event()

        async def worker() -> int:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()
            return 1

        first = worker()
        second = worker()
        owner = asyncio.create_task(
            async_utils.gather_with_concurrency(1, first, second)
        )
        await started.wait()
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner
        assert cleaned.is_set()
        assert inspect.getcoroutinestate(first) == inspect.CORO_CLOSED
        assert inspect.getcoroutinestate(second) == inspect.CORO_CLOSED

    asyncio.run(scenario())


@pytest.mark.parametrize("limit", [0, True, 1.5])
def test_gather_invalid_limit_closes_submitted_coroutines(
    limit: int,
) -> None:
    async def worker() -> int:
        return 1

    async def scenario() -> None:
        coroutine = worker()
        with pytest.raises(ValueError):
            await async_utils.gather_with_concurrency(limit, coroutine)
        assert inspect.getcoroutinestate(coroutine) == inspect.CORO_CLOSED

    asyncio.run(scenario())


@pytest.mark.parametrize("p", [0, -1, math.nan, -math.inf])
def test_invalid_norm_orders_are_rejected_even_for_empty_vectors(
    p: float,
) -> None:
    with pytest.raises(ValueError, match="positive"):
        vector_norm([], p=p)


def test_async_throttle_executes_first_call_and_retries_failed_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        calls = 0

        @async_utils.async_throttle(100)
        async def operation() -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise LookupError("first call fails")
            return calls

        monkeypatch.setattr(async_utils.time, "monotonic", lambda: 0.0)
        with pytest.raises(LookupError):
            await operation()
        assert await operation() == 2
        assert await operation() == 2
        assert calls == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("seconds", [math.nan, math.inf, -math.inf, -1])
def test_async_throttle_rejects_invalid_intervals(
    seconds: float,
) -> None:
    with pytest.raises(ValueError):
        async_utils.async_throttle(seconds)


@pytest.mark.parametrize("error", [NotImplementedError, RuntimeError])
def test_async_signal_restore_handles_unsupported_loop_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    error: type[Exception],
) -> None:
    loop = Mock()
    loop.remove_signal_handler.side_effect = error
    restore = Mock()
    monkeypatch.setattr(signals.signal, "signal", restore)
    registration = signals.AsyncSignalRegistration(loop, (2,), {2: "old"})
    registration.restore()
    registration.restore()
    restore.assert_called_once_with(2, "old")
    assert registration.restored


def test_lease_heartbeat_context_drains_cancellation_and_lease_loss() -> None:
    async def renew() -> bool:
        return True

    async def fail() -> None:
        raise LeaseLostError("expired")

    async def scenario() -> None:
        heartbeat = LeaseHeartbeat(renew, interval=100)
        async with heartbeat:
            await asyncio.sleep(0)
        assert heartbeat._task is not None and heartbeat._task.done()
        heartbeat._task = asyncio.create_task(fail())
        await asyncio.sleep(0)
        await heartbeat.__aexit__(None, None, None)

    asyncio.run(scenario())


def test_lease_exit_preserves_caller_cancellation_during_cleanup() -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        cleaning = asyncio.Event()
        release = asyncio.Event()
        cleaned = asyncio.Event()

        async def renew() -> bool:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await release.wait()
                cleaned.set()
            return True

        async def owner() -> None:
            async with LeaseHeartbeat(renew, interval=100):
                await started.wait()

        task = asyncio.create_task(owner())
        await cleaning.wait()
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cleaned.is_set()

    asyncio.run(scenario())


@pytest.mark.skipif(commands.os.name != "posix", reason="POSIX process groups")
def test_process_cleanup_accepts_already_exited_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def wait() -> int:
        return 0

    kill = Mock(side_effect=ProcessLookupError)
    monkeypatch.setattr(commands.os, "killpg", kill)
    process = SimpleNamespace(pid=123, wait=wait)
    asyncio.run(commands._stop_process(process, terminate_grace=1))
    kill.assert_called_once()


def test_noise_capture_accepts_unreadable_governor_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Path, "glob", lambda *args: [Path("/fake/governor")])
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=PermissionError))
    assert capture_noise_info().cpu_governors == ()


def test_process_metrics_integrates_rss_over_sample_intervals() -> None:
    profile = SimpleNamespace(
        wall_seconds=3.0,
        samples=(
            SimpleNamespace(elapsed=0.0, rss_bytes=10),
            SimpleNamespace(elapsed=1.0, rss_bytes=20),
            SimpleNamespace(elapsed=3.0, rss_bytes=30),
        ),
        average_cpu_cores=0.5,
        read_bytes=6,
        write_bytes=12,
        peak_rss_bytes=30,
        peak_pss_bytes=15,
    )
    metrics = process_metrics(profile)
    assert metrics["rss_byte_seconds"] == 50
    assert metrics["read_bytes_per_second"] == 2
