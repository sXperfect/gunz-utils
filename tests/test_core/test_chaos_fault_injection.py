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

    err_start = "start_time must be a finite non-negative number"
    err_sec = "seconds must be a finite non-negative number"

    with pytest.raises(ValueError, match=err_start):
        VirtualClock(start_time=-1.0)

    with pytest.raises(ValueError, match=err_start):
        VirtualClock(start_time=True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=err_start):
        VirtualClock(start_time=float("nan"))

    with pytest.raises(ValueError, match=err_start):
        VirtualClock(start_time=float("inf"))

    with pytest.raises(ValueError, match=err_sec):
        clock.advance(-0.5)

    with pytest.raises(ValueError, match=err_sec):
        clock.advance(True)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=err_sec):
        clock.advance(float("nan"))

    with pytest.raises(ValueError, match=err_sec):
        clock.advance(float("inf"))

    with pytest.raises(ValueError, match="advancing clock results in non-finite time"):
        clock.advance(1e308)
        clock.advance(1e308)

    large_clock = VirtualClock(1e308)
    large_ns = large_clock.now_ns()
    assert isinstance(large_ns, int)
    assert large_ns > 0


def test_faulty_stream_bounds_validation() -> None:
    buf = io.BytesIO()
    for kw, bad_val in [
        ("max_read_bytes", -1),
        ("max_read_bytes", True),
        ("max_write_bytes", -2),
        ("max_write_bytes", "five"),
        ("fail_read_after", -1),
        ("fail_write_after", -5),
    ]:
        with pytest.raises(ValueError, match="must be a non-negative integer or None"):
            FaultyStream(buf, **{kw: bad_val})  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="read_error must be callable"):
        FaultyStream(buf, read_error="not_callable")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="write_error must be callable"):
        FaultyStream(buf, write_error="not_callable")  # type: ignore[arg-type]


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


def test_await_boundary_chaos_cancellation() -> None:
    async def scenario() -> None:
        chaos = AwaitBoundaryChaos(cancel_at_step=3)

        await chaos.step()  # 1
        await chaos.step()  # 2

        with pytest.raises(asyncio.CancelledError, match="Injected await cancellation"):
            await chaos.step()  # 3

    asyncio.run(scenario())


def test_await_boundary_chaos_custom_fault() -> None:
    async def scenario() -> None:
        chaos = AwaitBoundaryChaos(
            fail_at_step=2,
            exception_factory=lambda: InjectedFault("custom failure"),
        )

        await chaos.step()  # 1

        with pytest.raises(InjectedFault, match="custom failure"):
            await chaos.step()  # 2

    asyncio.run(scenario())


def test_await_boundary_chaos_validation() -> None:
    for kw, bad_val in [
        ("cancel_at_step", 0),
        ("cancel_at_step", -1),
        ("cancel_at_step", True),
        ("fail_at_step", 0),
        ("fail_at_step", -2),
        ("fail_at_step", True),
    ]:
        with pytest.raises(ValueError, match="must be a positive integer or None"):
            AwaitBoundaryChaos(**{kw: bad_val})  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="exception_factory must be callable"):
        AwaitBoundaryChaos(exception_factory="not_callable")  # type: ignore[arg-type]
