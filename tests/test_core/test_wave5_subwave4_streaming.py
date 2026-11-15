"""Tests for Wave 5 Sub-Wave 4: Streaming Protocols & Pipeline Transformations."""

import asyncio
import pytest

from gunz_utils.streaming import (
    AsyncDelimitedReader,
    AsyncStreamBuffer,
    stream_batch,
    stream_drain,
    stream_drop_while,
    stream_filter_none,
    stream_interleave,
    stream_peek,
    stream_take_while,
    stream_tee,
    stream_windowed,
)


def test_stream_windowed():
    data = [1, 2, 3, 4, 5]
    assert list(stream_windowed(data, size=3, step=1)) == [
        (1, 2, 3),
        (2, 3, 4),
        (3, 4, 5),
    ]
    assert list(stream_windowed(data, size=2, step=2)) == [(1, 2), (3, 4)]
    assert list(stream_windowed(data, size=2, step=3)) == [(1, 2), (4, 5)]
    assert list(stream_windowed(data, size=10)) == []

    with pytest.raises(ValueError):
        list(stream_windowed(data, size=0))
    with pytest.raises(ValueError):
        list(stream_windowed(data, size=2, step=0))


def test_stream_batch():
    data = range(7)
    batches = list(stream_batch(data, max_size=3))
    assert batches == [[0, 1, 2], [3, 4, 5], [6]]
    assert list(stream_batch([], max_size=5)) == []

    with pytest.raises(ValueError):
        list(stream_batch(data, max_size=0))


def test_stream_filter_none():
    data = [1, None, 2, None, None, 3, 0, False, ""]
    assert list(stream_filter_none(data)) == [1, 2, 3, 0, False, ""]


def test_stream_interleave():
    it1 = [1, 2, 3]
    it2 = ["a", "b"]
    it3 = [True, False, None, "extra"]
    res = list(stream_interleave(it1, it2, it3))
    assert res == [1, "a", True, 2, "b", False, 3, None, "extra"]
    assert list(stream_interleave()) == []


def test_stream_take_and_drop_while():
    data = [1, 3, 5, 6, 7, 8]
    assert list(stream_take_while(data, lambda x: x % 2 != 0)) == [1, 3, 5]
    assert list(stream_drop_while(data, lambda x: x % 2 != 0)) == [6, 7, 8]


def test_stream_peek_and_drain():
    data = [10, 20, 30, 40]
    peeked, it = stream_peek(data, n=2)
    assert peeked == [10, 20]
    assert list(it) == [10, 20, 30, 40]

    peeked2, it2 = stream_peek([1, 2], n=5)
    assert peeked2 == [1, 2]
    assert list(it2) == [1, 2]

    assert stream_drain(range(50)) == 50


def test_stream_tee():
    orig = [1, 2, 3]
    t1, t2, t3 = stream_tee(orig, n=3)
    assert list(t1) == [1, 2, 3]
    assert list(t2) == [1, 2, 3]
    assert list(t3) == [1, 2, 3]


@pytest.mark.asyncio
async def test_async_stream_buffer():
    buf = AsyncStreamBuffer(max_bytes=100)
    assert not buf.is_eof()
    await buf.write(b"hello ")
    await buf.write(b"world\n")
    read1 = await buf.read(5)
    assert read1 == b"hello"
    read2 = await buf.read(1)
    assert read2 == b" "
    buf.write_eof()
    read3 = await buf.read()
    assert read3 == b"world\n"
    assert buf.is_eof()
    assert await buf.read() == b""

    with pytest.raises(RuntimeError):
        await buf.write(b"fail")


@pytest.mark.asyncio
async def test_async_delimited_reader():
    buf = AsyncStreamBuffer()
    reader = AsyncDelimitedReader(buf)

    async def producer():
        await buf.write(b"line1\nline2\r\nline3")
        buf.write_eof()

    asyncio.create_task(producer())

    l1 = await reader.read_until(b"\n")
    assert l1 == b"line1\n"
    l2 = await reader.read_until(b"\r\n")
    assert l2 == b"line2\r\n"
    l3 = await reader.read_until(b"\n")
    assert l3 == b"line3"
