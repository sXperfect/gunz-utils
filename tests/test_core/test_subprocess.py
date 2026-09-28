from __future__ import annotations

import asyncio
import sys
import unittest

from gunz_utils.subprocess import (
    CommandError,
    CommandOutputLimitError,
    run_command,
    run_command_async,
)


class TestSubprocess(unittest.TestCase):
    def test_capture(self) -> None:
        result = run_command([sys.executable, "-c", "print('ok')"], check=True)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertEqual(result.returncode, 0)

    def test_checked_failure(self) -> None:
        with self.assertRaises(CommandError):
            run_command([sys.executable, "-c", "raise SystemExit(3)"], check=True)

    def test_command_error_message_does_not_echo_arguments(self) -> None:
        secret = "command-line-secret"
        with self.assertRaises(CommandError) as cm:
            run_command(
                [sys.executable, "-c", "raise SystemExit(3)", secret],
                check=True,
            )
        self.assertNotIn(secret, str(cm.exception))
        self.assertIn(secret, cm.exception.result.args)

    def test_output_limit(self) -> None:
        with self.assertRaises(CommandOutputLimitError):
            run_command(
                [sys.executable, "-c", "print('x' * 100)"],
                max_output_bytes=10,
            )


class TestAsyncSubprocess(unittest.IsolatedAsyncioTestCase):
    async def test_async_capture(self) -> None:
        result = await run_command_async(
            [sys.executable, "-c", "print('async')"],
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "async")

    async def test_async_output_limit(self) -> None:
        with self.assertRaises(CommandOutputLimitError):
            await run_command_async(
                [sys.executable, "-c", "print('x' * 100)"],
                max_output_bytes=10,
            )

    async def test_timeout_raises(self) -> None:
        with self.assertRaises(TimeoutError):
            await run_command_async(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                timeout=0.01,
                terminate_grace=0.01,
            )

    async def test_cancellation_propagates(self) -> None:
        task = asyncio.create_task(
            run_command_async(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                terminate_grace=0.01,
            )
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


if __name__ == "__main__":
    unittest.main()
