from __future__ import annotations

import asyncio
import sys
import unittest

from gunz_utils.benchmark import profile_command
from gunz_utils.concurrency import gather_limited
from gunz_utils.resilience import AsyncCircuitBreaker, CircuitState


class TestDeepAuditRound2(unittest.IsolatedAsyncioTestCase):
    async def test_gather_never_swallows_cancellation(self) -> None:
        async def cancelled() -> None:
            raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await gather_limited(
                [cancelled()],
                limit=1,
                return_exceptions=True,
            )

    async def test_half_open_cancellation_releases_probe(self) -> None:
        breaker = AsyncCircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0,
        )

        async def fail() -> None:
            raise OSError("down")

        with self.assertRaises(OSError):
            await breaker.call(fail)
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)

        started = asyncio.Event()

        async def wait() -> None:
            started.set()
            await asyncio.sleep(10)

        task = asyncio.create_task(breaker.call(wait))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task

        async def recover() -> str:
            return "ok"

        self.assertEqual(await breaker.call(recover), "ok")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux /proc required")
    async def test_profile_has_no_empty_post_exit_tail(self) -> None:
        profile = profile_command(
            [sys.executable, "-c", "import time;time.sleep(.02)"],
            interval=0.002,
        )
        self.assertTrue(profile.samples)
        self.assertGreater(profile.samples[-1].process_count, 0)


if __name__ == "__main__":
    unittest.main()
