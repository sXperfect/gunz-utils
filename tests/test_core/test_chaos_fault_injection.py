"""Tests for chaos and fault-injection primitives."""

from __future__ import annotations

import asyncio
import io

import pytest

from gunz_utils.faults import (
    AwaitBoundaryChaos,
    FaultyStream,
    InjectedFault,
    VirtualClock,
)


def test_virtual_clock_advance_and_bounds() -> None:
    clock = VirtualClock(start_time=100.0)
    assert clock.now() == 100.0
    assert clock.now_ns() == 100_000_000_000

    clock.advance(2.5)
    assert clock.now() == 102.5
    assert clock.now_ns() == 102_500_000_000

    with pytest.raises(ValueError, match="start_time must be a non-negative number"):
        VirtualClock(start_time=-1.0)

    with pytest.raises(ValueError, match="start_time must be a non-negative number"):
        VirtualClock(start_time=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="seconds must be a non-negative number"):
        clock.advance(-0.5)

    with pytest.raises(ValueError, match="seconds must be a non-negative number"):
        clock.advance(True)  # type: ignore[arg-type]


def test_faulty_stream_short_writes_and_failures() -> None:
    buf = io.BytesIO()
    stream = FaultyStream(buf, max_write_bytes=4, fail_write_after=2)

    written1 = stream.write(b"abcdefgh")
    assert written1 == 4
    assert buf.getvalue() == b"abcd"

    written2 = stream.write(b"12345678")
    assert written2 == 4
    assert buf.getvalue() == b"abcd1234"

    with pytest.raises(OSError, match="Injected stream write error"):
        stream.write(b"boom")


def test_faulty_stream_short_reads_and_failures() -> None:
    buf = io.BytesIO(b"0123456789abcdef")
    stream = FaultyStream(buf, max_read_bytes=3, fail_read_after=2)

    assert stream.read(10) == b"012"
    assert stream.read(10) == b"345"

    with pytest.raises(OSError, match="Injected stream read error"):
        stream.read(10)


@pytest.mark.asyncio
async def test_await_boundary_chaos_cancellation() -> None:
    chaos = AwaitBoundaryChaos(cancel_at_step=3)

    await chaos.step()  # 1
    await chaos.step()  # 2

    with pytest.raises(asyncio.CancelledError, match="Injected await cancellation"):
        await chaos.step()  # 3


@pytest.mark.asyncio
async def test_await_boundary_chaos_custom_fault() -> None:
    chaos = AwaitBoundaryChaos(
        fail_at_step=2,
        exception_factory=lambda: InjectedFault("custom failure"),
    )

    await chaos.step()  # 1

    with pytest.raises(InjectedFault, match="custom failure"):
        await chaos.step()  # 2
