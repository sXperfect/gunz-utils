from __future__ import annotations

import asyncio
import unittest

from gunz_utils.retry import async_retry, retry


class TestRetry(unittest.TestCase):
    def test_sync_retries_then_succeeds(self) -> None:
        calls = 0

        @retry(attempts=3, base_delay=0, jitter=False)
        def work() -> int:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ValueError("retry")
            return 42

        self.assertEqual(work(), 42)
        self.assertEqual(calls, 3)

    def test_invalid_attempts(self) -> None:
        with self.assertRaises(ValueError):
            retry(attempts=0)


class TestAsyncRetry(unittest.IsolatedAsyncioTestCase):
    async def test_async_retries_then_succeeds(self) -> None:
        calls = 0

        @async_retry(attempts=2, base_delay=0, jitter=False)
        async def work() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("temporary")
            return "ok"

        self.assertEqual(await work(), "ok")
        self.assertEqual(calls, 2)

    async def test_cancellation_is_not_retried(self) -> None:
        calls = 0

        @async_retry(attempts=3, base_delay=0)
        async def work() -> None:
            nonlocal calls
            calls += 1
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await work()
        self.assertEqual(calls, 1)
