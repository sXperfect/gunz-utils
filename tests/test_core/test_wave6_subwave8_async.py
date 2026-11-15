"""Tests for Wave 6 Sub-Wave 8: Asynchronous Flow Control, Throttling & Concurrency Limits."""

import asyncio
import time
import pytest

from gunz_utils.async_utils import (
    AsyncBarrier,
    AsyncPeriodicTask,
    async_debounce,
    async_first_completed,
    async_retry,
    async_throttle,
    async_timeout,
    gather_with_concurrency,
    run_in_executor,
)


@pytest.mark.asyncio
async def test_gather_with_concurrency():
    running = 0
    max_running = 0

    async def worker(idx):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.01)
        running -= 1
        return idx * 2

    results = await gather_with_concurrency(2, *(worker(i) for i in range(5)))
    assert results == [0, 2, 4, 6, 8]
    assert max_running <= 2


@pytest.mark.asyncio
async def test_async_timeout():
    async with async_timeout(0.1):
        await asyncio.sleep(0.01)

    with pytest.raises(TimeoutError):
        async with async_timeout(0.02):
            await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_async_retry():
    attempts = 0

    @async_retry(retries=3, delay=0.01, backoff=1.5)
    async def flaky():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ValueError("temporary error")
        return "success"

    res = await flaky()
    assert res == "success"
    assert attempts == 3


@pytest.mark.asyncio
async def test_async_throttle():
    calls = 0

    @async_throttle(0.05)
    async def ping():
        nonlocal calls
        calls += 1
        return calls

    assert await ping() == 1
    assert await ping() == 1  # throttled
    await asyncio.sleep(0.06)
    assert await ping() == 2


@pytest.mark.asyncio
async def test_async_first_completed():
    async def slow():
        await asyncio.sleep(0.1)
        return "slow"

    async def fast():
        await asyncio.sleep(0.01)
        return "fast"

    res = await async_first_completed(slow(), fast())
    assert res == "fast"


@pytest.mark.asyncio
async def test_async_barrier():
    barrier = AsyncBarrier(parties=3)
    arrivals = []

    async def attendee(idx):
        pos = await barrier.wait()
        arrivals.append((idx, pos))

    await asyncio.gather(*(attendee(i) for i in range(3)))
    assert len(arrivals) == 3


@pytest.mark.asyncio
async def test_async_periodic_task():
    counter = 0

    async def tick():
        nonlocal counter
        counter += 1

    task = AsyncPeriodicTask(tick, interval=0.02)
    task.start()
    assert task.is_running
    await asyncio.sleep(0.05)
    task.stop()
    assert not task.is_running
    assert counter >= 2


@pytest.mark.asyncio
async def test_run_in_executor():
    def blocking_add(a, b):
        return a + b

    res = await run_in_executor(blocking_add, 10, 20)
    assert res == 30
