from __future__ import annotations

import asyncio
import unittest

from gunz_utils.async_utils import cancel_and_wait, with_timeout
from gunz_utils.collections import group_by, index_by, partition, unique
from gunz_utils.config import env_overrides, merge_configs
from gunz_utils.diagnostics import exception_dict
from gunz_utils.env import env, env_bool
from gunz_utils.identifiers import deterministic_id, new_id, short_id
from gunz_utils.rate_limit import AsyncRateLimiter
from gunz_utils.result import Result
from gunz_utils.testing import eventually, temporary_env
from gunz_utils.time_utils import expired, monotonic_deadline, remaining, utc_now


class TestCollections(unittest.TestCase):
    def test_transforms(self) -> None:
        self.assertEqual(unique([1, 1, 2]), [1, 2])\n        self.assertEqual(unique([[1], [1], [2]]), [[1], [2]])
        self.assertEqual(group_by(["a", "bb"], len), {1: ["a"], 2: ["bb"]})
        self.assertEqual(index_by(["a", "bb"], len), {1: "a", 2: "bb"})
        self.assertEqual(partition(range(4), lambda x: x % 2 == 0), ([0, 2], [1, 3]))


class TestEnvConfig(unittest.TestCase):
    def test_typed_env(self) -> None:
        with temporary_env({"GUNZ_TEST_INT": "7", "GUNZ_TEST_BOOL": "true"}):
            self.assertEqual(env("GUNZ_TEST_INT", cast=int), 7)
            self.assertTrue(env_bool("GUNZ_TEST_BOOL"))

    def test_missing_env(self) -> None:
        with temporary_env({"GUNZ_MISSING": None}):
            with self.assertRaises(KeyError):
                env("GUNZ_MISSING")

    def test_config_layers(self) -> None:
        self.assertEqual(
            merge_configs({"a": {"x": 1}}, {"a": {"y": 2}}),
            {"a": {"x": 1, "y": 2}},
        )
        self.assertEqual(
            env_overrides({"APP_DB__HOST": "localhost"}, prefix="APP"),
            {"db": {"host": "localhost"}},
        )


class TestIdsTimeResult(unittest.TestCase):
    def test_ids(self) -> None:
        self.assertNotEqual(new_id(), new_id())
        self.assertEqual(deterministic_id("ns", "x"), deterministic_id("ns", "x"))
        self.assertEqual(len(short_id("x")), 12)

    def test_time(self) -> None:
        self.assertIsNotNone(utc_now().tzinfo)
        deadline = monotonic_deadline(0.05)
        self.assertGreater(remaining(deadline), 0)
        self.assertFalse(expired(deadline))

    def test_result(self) -> None:
        self.assertEqual(Result[int, str].ok(3).unwrap(), 3)
        with self.assertRaises(RuntimeError):
            Result[int, str].err("bad").unwrap()


class TestDiagnosticsTesting(unittest.TestCase):
    def test_exception_context_is_redacted(self) -> None:
        data = exception_dict(ValueError("bad"), context={"password": "secret"})
        self.assertEqual(data["context"], {"password": "****"})

    def test_eventually(self) -> None:
        eventually(lambda: True, timeout=0)


class TestAsyncFoundation(unittest.IsolatedAsyncioTestCase):
    async def test_rate_limiter(self) -> None:
        limiter = AsyncRateLimiter(100, capacity=1)
        await limiter.acquire()

    async def test_timeout(self) -> None:
        self.assertEqual(await with_timeout(asyncio.sleep(0, result=3), 1), 3)

    async def test_cancel_and_wait(self) -> None:
        task = asyncio.create_task(asyncio.sleep(10))
        await cancel_and_wait(task)
        self.assertTrue(task.cancelled())


if __name__ == "__main__":
    unittest.main()
