from __future__ import annotations

import sys
import unittest

from gunz_utils.subprocess import CommandError, run_command, run_command_async


class TestSubprocess(unittest.TestCase):
    def test_capture(self) -> None:
        result = run_command([sys.executable, "-c", "print('ok')"], check=True)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertEqual(result.returncode, 0)

    def test_checked_failure(self) -> None:
        with self.assertRaises(CommandError):
            run_command([sys.executable, "-c", "raise SystemExit(3)"], check=True)


class TestAsyncSubprocess(unittest.IsolatedAsyncioTestCase):
    async def test_async_capture(self) -> None:
        result = await run_command_async(
            [sys.executable, "-c", "print('async')"],
            check=True,
        )
        self.assertEqual(result.stdout.strip(), "async")
