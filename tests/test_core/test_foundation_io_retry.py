from __future__ import annotations

import asyncio
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from gunz_utils.io import atomic_json_write, atomic_write
from gunz_utils.retry import (
    RetryPolicy,
    async_run_with_retry,
    run_with_retry,
)
from gunz_utils.streaming import (
    BoundedWriter,
    DigestWriter,
    copy_and_hash,
)


class PartialWriter(io.BytesIO):
    def write(self, data: Any) -> int:
        return super().write(bytes(data[:1]))


class TestRetryPolicy(unittest.TestCase):
    def test_retries_retryable_results(self) -> None:
        values = iter(["pending", "pending", "ready"])
        events = []
        result = run_with_retry(
            lambda: next(values),
            RetryPolicy(
                attempts=3,
                base_delay=0,
                jitter=False,
                retry_if_result=lambda value: value == "pending",
            ),
            on_retry=events.append,
        )
        self.assertEqual(result, "ready")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].result, "pending")

    def test_exception_predicate_can_stop_retry(self) -> None:
        calls = 0

        def work() -> int:
            nonlocal calls
            calls += 1
            raise ValueError("fatal")

        with self.assertRaises(ValueError):
            run_with_retry(
                work,
                RetryPolicy(
                    attempts=3,
                    base_delay=0,
                    jitter=False,
                    retry_if_exception=lambda exc: False,
                ),
            )
        self.assertEqual(calls, 1)


class TestAsyncRetryPolicy(unittest.IsolatedAsyncioTestCase):
    async def test_async_result_retry(self) -> None:
        values = iter([503, 200])

        async def work() -> int:
            return next(values)

        result = await async_run_with_retry(
            work,
            RetryPolicy(
                attempts=2,
                base_delay=0,
                jitter=False,
                retry_if_result=lambda status: status >= 500,
            ),
        )
        self.assertEqual(result, 200)

    async def test_cancellation_propagates(self) -> None:
        async def work() -> None:
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await async_run_with_retry(
                work,
                RetryPolicy(attempts=3, base_delay=0),
            )


class TestStreamingWriters(unittest.TestCase):
    def test_bounded_writer_does_not_partially_exceed_limit(self) -> None:
        output = io.BytesIO()
        writer = BoundedWriter(output, max_bytes=3)
        writer.write(b"ab")
        with self.assertRaises(ValueError):
            writer.write(b"cd")
        self.assertEqual(output.getvalue(), b"ab")

    def test_bounded_writer_handles_partial_writes(self) -> None:
        output = PartialWriter()
        writer = BoundedWriter(output, max_bytes=3)
        self.assertEqual(writer.write(b"abc"), 3)
        self.assertEqual(writer.bytes_written, 3)
        self.assertEqual(output.getvalue(), b"abc")

    def test_digest_writer_tracks_partial_writes(self) -> None:
        output = PartialWriter()
        writer = DigestWriter(output)
        writer.write(b"abc")
        self.assertEqual(writer.bytes_written, 3)
        self.assertEqual(
            writer.hexdigest,
            hashlib.sha256(b"abc").hexdigest(),
        )

    def test_copy_and_hash(self) -> None:
        output = io.BytesIO()
        result = copy_and_hash(
            io.BytesIO(b"abcdef"),
            output,
            chunk_size=2,
            max_bytes=6,
        )
        self.assertEqual(output.getvalue(), b"abcdef")
        self.assertEqual(result.bytes_written, 6)
        self.assertEqual(
            result.hexdigest,
            hashlib.sha256(b"abcdef").hexdigest(),
        )


class TestAtomicJSON(unittest.TestCase):
    def test_atomic_json_write_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "value.json"
            atomic_json_write(
                path,
                {"b": 2, "a": 1},
                mkdir=True,
            )
            text = path.read_text()
            self.assertEqual(
                json.loads(text),
                {"a": 1, "b": 2},
            )
            self.assertLess(
                text.find('"a"'),
                text.find('"b"'),
            )

    def test_durable_binary_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "value.bin"
            atomic_write(
                path,
                b"abc",
                mode="wb",
                durable=True,
            )
            self.assertEqual(path.read_bytes(), b"abc")


if __name__ == "__main__":
    unittest.main()
