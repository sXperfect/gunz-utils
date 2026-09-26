from __future__ import annotations

import asyncio
import unittest

from gunz_utils.instrumentation import Counter, Timer
from gunz_utils.pipeline import worker_map
from gunz_utils.typed_config import convert, parse_bool


class TestM11M13(unittest.IsolatedAsyncioTestCase):
    async def test_worker_map(self) -> None:
        async def work(value: int) -> int:
            await asyncio.sleep(0)
            return value * 2

        values = [value async for value in worker_map(work, range(10), workers=3)]
        self.assertEqual(sorted(values), [value * 2 for value in range(10)])

    async def test_instrumentation_and_config(self) -> None:
        counter = Counter()
        self.assertEqual(counter.add(), 1)
        with Timer("x") as timer:
            await asyncio.sleep(0)
        self.assertTrue(timer.result and timer.result.success)
        value = convert("true", parse_bool, source="env:FLAG")
        self.assertTrue(value.value)
        self.assertEqual(value.source, "env:FLAG")


if __name__ == "__main__":
    unittest.main()
