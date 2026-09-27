"""Tests for backend-neutral renewable lease coordination."""

from __future__ import annotations

import asyncio

import pytest

from gunz_utils.leases import (
    LeaseLostError,
    LeaseTiming,
    run_with_lease_heartbeat,
)


def test_lease_timing_validates_renewal_cadence() -> None:
    timing = LeaseTiming(
        lease_seconds=120.0,
        heartbeat_interval=30.0,
    )

    assert timing.lease_seconds == pytest.approx(120.0)

    with pytest.raises(ValueError, match="shorter"):
        LeaseTiming(
            lease_seconds=30.0,
            heartbeat_interval=30.0,
        )


def test_operation_completion_cancels_heartbeat() -> None:
    async def scenario() -> str:
        renew_calls = 0

        async def renew() -> bool:
            nonlocal renew_calls
            renew_calls += 1
            return True

        async def work() -> str:
            return "done"

        result = await run_with_lease_heartbeat(
            work,
            renew,
            heartbeat_interval=3600.0,
        )
        assert renew_calls == 0
        return result

    assert asyncio.run(scenario()) == "done"


def test_lost_lease_cancels_inflight_operation() -> None:
    async def scenario() -> bool:
        cancelled = asyncio.Event()

        async def renew() -> bool:
            return False

        async def work() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with pytest.raises(LeaseLostError):
            await run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=60.0,
                renew_immediately=True,
            )
        return cancelled.is_set()

    assert asyncio.run(scenario())


def test_renewal_exception_cancels_operation_and_propagates() -> None:
    async def scenario() -> bool:
        cancelled = asyncio.Event()

        async def renew() -> bool:
            raise RuntimeError("renewal failed")

        async def work() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with pytest.raises(RuntimeError, match="renewal failed"):
            await run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=60.0,
                renew_immediately=True,
            )
        return cancelled.is_set()

    assert asyncio.run(scenario())


def test_operation_exception_cancels_heartbeat_and_propagates() -> None:
    async def scenario() -> None:
        async def renew() -> bool:
            return True

        async def work() -> None:
            raise ValueError("work failed")

        with pytest.raises(ValueError, match="work failed"):
            await run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=3600.0,
            )

    asyncio.run(scenario())


def test_lease_runner_validates_callback_and_interval() -> None:
    async def noop() -> None:
        return None

    async def renew() -> bool:
        return True

    with pytest.raises(TypeError, match="operation"):
        asyncio.run(
            run_with_lease_heartbeat(
                object(),
                renew,
                heartbeat_interval=1.0,
            )
        )

    with pytest.raises(ValueError, match="heartbeat_interval"):
        asyncio.run(
            run_with_lease_heartbeat(
                noop,
                renew,
                heartbeat_interval=0.0,
            )
        )



def test_lease_loss_wins_when_work_completes_in_same_turn() -> None:
    async def scenario() -> None:
        release = asyncio.Event()

        async def renew() -> bool:
            release.set()
            return False

        async def work() -> str:
            await release.wait()
            return "stale-result"

        with pytest.raises(LeaseLostError):
            await run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=60.0,
                renew_immediately=True,
            )

    asyncio.run(scenario())


def test_renew_callback_must_return_bool() -> None:
    async def scenario() -> None:
        cancelled = asyncio.Event()

        async def renew() -> bool:
            return 1

        async def work() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with pytest.raises(TypeError, match="must return bool"):
            await run_with_lease_heartbeat(
                work,
                renew,
                heartbeat_interval=60.0,
                renew_immediately=True,
            )
        assert cancelled.is_set()

    asyncio.run(scenario())
