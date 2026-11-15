"""Tests for Wave 7 Sub-Wave 7: Circular Buffers, Memory Pools & Chunk Allocators."""

from gunz_utils.memory import (
    ChunkedMemoryStream,
    MemoryChunkPool,
    SlidingByteBuffer,
)


def test_memory_chunk_pool():
    pool = MemoryChunkPool(chunk_size=1024, max_chunks=2)
    with pool.scoped() as c1:
        assert len(c1) == 1024
        c1[0] = 42

    # Should be returned to pool and reused
    c2 = pool.acquire()
    assert len(c2) == 1024
    pool.release(c2)


def test_sliding_byte_buffer():
    buf = SlidingByteBuffer(capacity=100)
    buf.write(b"hello world")
    assert len(buf) == 11
    assert buf.peek(5) == b"hello"
    assert len(buf) == 11  # peek doesn't consume

    assert buf.find(b"world") == 6
    assert buf.read(6) == b"hello "
    assert len(buf) == 5
    assert buf.read() == b"world"
    assert len(buf) == 0


def test_chunked_memory_stream():
    stream = ChunkedMemoryStream(chunk_size=4)
    written = stream.write(b"abcdefghij")  # 10 bytes -> across 3 chunks
    assert written == 10
    assert stream.getvalue() == b"abcdefghij"

    # Reading
    part1 = stream.read(3)
    assert part1 == b"abc"
    assert stream.tell() == 3

    part2 = stream.read(5)
    assert part2 == b"defgh"

    part3 = stream.read()
    assert part3 == b"ij"
    assert stream.read() == b""

    # Seek
    stream.seek(0)
    assert stream.read(4) == b"abcd"
