"""Tests for Wave 4 enhancements: plugins, serialization, and retry (#43–#56)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

import asyncio
import tempfile
import unittest
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.plugins import (
    GunzFileFinder,
    PluginInfo,
    load_module_from_path,
)
from gunz_utils.retry import (
    RetryExhaustedError,
    RetryPolicy,
    async_retry,
    async_run_with_retry,
    retry,
    run_with_retry,
)
from gunz_utils.serialization import (
    decode_json_object,
    json_dumps,
    json_loads,
    to_jsonable,
)


class TestWave4Plugins(unittest.TestCase):
    def test_item43_gunz_file_finder_prefix_independence(self) -> None:
        finder = GunzFileFinder()
        #? Non-registered module returns None
        self.assertIsNone(finder.find_spec("unregistered_mod_xyz_123"))

    def test_item44_load_module_from_path_cleanup_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "broken_plugin.py"
            bad_file.write_text(
    "raise RuntimeError('broken on load')",
     encoding="utf-8")
            with self.assertRaises(RuntimeError):
                load_module_from_path(bad_file, prefix="test_broken_mod_item44")
            #? Should have cleaned up registration
            finder = GunzFileFinder()
            self.assertIsNone(finder.find_spec("test_broken_mod_item44.broken_plugin"))

    def test_item45_load_module_from_path_prefix_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "good_mod.py"
            py_file.write_text("X = 1\n", encoding="utf-8")
            with self.assertRaises(TypeError):
                load_module_from_path(py_file, prefix=123)  # type: ignore[arg-type]
            with self.assertRaises(ValueError):
                load_module_from_path(py_file, prefix="invalid-identifier-name!")

    def test_item46_plugin_info_validation(self) -> None:
        with self.assertRaises(ValueError):
            PluginInfo(name="", value="pkg:obj", group="my.plugins")
        with self.assertRaises(ValueError):
            PluginInfo(name="  ", value="pkg:obj", group="my.plugins")
        with self.assertRaises(ValueError):
            PluginInfo(name="name", value="", group="my.plugins")
        with self.assertRaises(ValueError):
            PluginInfo(name="name", value="pkg:obj", group="")
        info = PluginInfo(name="my_plugin", value="pkg:obj", group="my.plugins")
        self.assertEqual(info.name, "my_plugin")
        self.assertEqual(info.value, "pkg:obj")
        self.assertEqual(info.group, "my.plugins")


class TestWave4Serialization(unittest.TestCase):
    def test_item47_to_jsonable_bytes_like_rejection(self) -> None:
        with self.assertRaises(TypeError):
            to_jsonable(b"hello")
        with self.assertRaises(TypeError):
            to_jsonable(bytearray(b"hello"))
        with self.assertRaises(TypeError):
            to_jsonable(memoryview(b"hello"))

    def test_item48_json_dumps_pretty_validation(self) -> None:
        with self.assertRaises(TypeError):
            json_dumps({"a": 1}, pretty="yes")  # type: ignore[arg-type]
        compact = json_dumps({"a": 1}, pretty=False)
        pretty = json_dumps({"a": 1}, pretty=True)
        self.assertIn("\n", pretty)
        self.assertNotIn("\n", compact)

    def test_item49_decode_json_object_bytes_like(self) -> None:
        data = b'{"hello": "world", "num": 42}'
        self.assertEqual(
    decode_json_object(
        bytearray(data)), {
            "hello": "world", "num": 42})
        self.assertEqual(
    decode_json_object(
        memoryview(data)), {
            "hello": "world", "num": 42})

    def test_item50_json_loads_bytes_like_and_bounds(self) -> None:
        data = b'{"key": [1, 2, 3]}'
        self.assertEqual(json_loads(bytearray(data)), {"key": [1, 2, 3]})
        self.assertEqual(json_loads(memoryview(data)), {"key": [1, 2, 3]})
        #? max_bytes bound
        with self.assertRaises(ValueError):
            json_loads(data, max_bytes=5)


class TestWave4Retry(unittest.TestCase):
    def test_item51_retry_policy_validation(self) -> None:
        with self.assertRaises(TypeError):
            RetryPolicy(exceptions="ValueError")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            RetryPolicy(jitter="yes")  # type: ignore[arg-type]
        #? Valid tuple normalization
        policy = RetryPolicy(exceptions=[ValueError, KeyError])
        self.assertIsInstance(policy.exceptions, tuple)
        self.assertEqual(policy.exceptions, (ValueError, KeyError))

    def test_item52_retry_policy_delay_attempt_int_check(self) -> None:
        policy = RetryPolicy()
        with self.assertRaises(ValueError):
            policy.delay_for_attempt(True)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            policy.delay_for_attempt("1")  # type: ignore[arg-type]
        self.assertGreaterEqual(policy.delay_for_attempt(1), 0.0)

    def test_item53_retry_and_async_retry_eager_validation(self) -> None:
        with self.assertRaises(TypeError):
            retry(exceptions="ValueError")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            async_retry(exceptions="ValueError")  # type: ignore[arg-type]

    def test_item54_run_with_retry_never_catches_system_exits(self) -> None:
        def raise_system_exit() -> None:
            raise SystemExit(42)

        policy = RetryPolicy(exceptions=(BaseException,))
        with self.assertRaises(SystemExit):
            run_with_retry(raise_system_exit, policy=policy)

        async def async_raise_system_exit() -> None:
            raise SystemExit(42)

        with self.assertRaises(SystemExit):
            asyncio.run(async_run_with_retry(async_raise_system_exit, policy=policy))

    def test_item55_retry_exhausted_error_validation_and_export(self) -> None:
        with self.assertRaises(TypeError):
            RetryExhaustedError(
    "msg",
    attempts=True,
    total_delay=1.0,
     last_exception=ValueError())  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            RetryExhaustedError(
    "msg",
    attempts=0,
    total_delay=1.0,
     last_exception=ValueError())
        with self.assertRaises(ValueError):
            RetryExhaustedError(
    "msg",
    attempts=1,
    total_delay=-0.5,
     last_exception=ValueError())

        err = RetryExhaustedError(
    "attempts exhausted",
    attempts=3,
    total_delay=1.5,
     last_exception=ValueError("boom"))
        self.assertIsInstance(err, RuntimeError)
        self.assertEqual(err.attempts, 3)
        self.assertEqual(err.total_delay, 1.5)
        self.assertIsInstance(err.last_exception, ValueError)


if __name__ == "__main__":
    unittest.main()
