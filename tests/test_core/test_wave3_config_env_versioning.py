"""Tests for Wave 3: Config, env, parsing, typed_config, deprecation, result, versioning, identifiers, models."""

from __future__ import annotations

import asyncio
from types import MappingProxyType
import unittest
import warnings

from gunz_utils.config import env_overrides, merge_configs
from gunz_utils.deprecation import GunzDeprecationWarning, deprecated
from gunz_utils.env import env, env_float, env_int, env_list
from gunz_utils.identifiers import is_valid_uuid, short_id
from gunz_utils.parsing import parse_bool, safe_float, safe_int
from gunz_utils.result import Result
from gunz_utils.sentinels import UNSET
from gunz_utils.typed_config import ConfigValue, convert
from gunz_utils.versioning import (
    SchemaMigrationError,
    SchemaMigrator,
    VersionedEnvelope,
)


class TestConfigWave3(unittest.TestCase):
    def test_merge_configs_validation(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            merge_configs({"a": 1}, "not_a_mapping")  # type: ignore[arg-type]
        self.assertIn("config at index 1 must be a Mapping", str(ctx.exception))

    def test_env_overrides_validation_and_collision(self) -> None:
        with self.assertRaises(TypeError):
            env_overrides("not_a_mapping", prefix="APP")  # type: ignore[arg-type]

        # Case-insensitive collision
        environ = {
            "APP_DATABASE_URL": "postgres://localhost",
            "app_database_url": "mysql://localhost",
        }
        with self.assertRaises(ValueError) as ctx:
            env_overrides(environ, prefix="APP")
        self.assertIn("collides with", str(ctx.exception))


class TestEnvWave3(unittest.TestCase):
    def test_env_name_validation(self) -> None:
        with self.assertRaises(ValueError):
            env("")
        with self.assertRaises(ValueError):
            env(None)  # type: ignore[arg-type]

    def test_env_int(self) -> None:
        environ = {"TEST_PORT": "8080", "BAD_INT": "abc"}
        import os

        old = os.environ.copy()
        os.environ.update(environ)
        try:
            self.assertEqual(env_int("TEST_PORT"), 8080)
            self.assertEqual(env_int("MISSING_PORT", default=3000), 3000)
            with self.assertRaises(ValueError):
                env_int("TEST_PORT", max=8000)
            with self.assertRaises(ValueError):
                env_int("BAD_INT")
            with self.assertRaises(KeyError):
                env_int("MISSING_PORT")
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_env_float(self) -> None:
        import os

        old = os.environ.copy()
        os.environ.update({"TEST_RATE": "1.25", "BAD_FLOAT": "foo"})
        try:
            self.assertEqual(env_float("TEST_RATE"), 1.25)
            self.assertEqual(env_float("MISSING_RATE", default=0.5), 0.5)
            with self.assertRaises(ValueError):
                env_float("TEST_RATE", max=1.0)
            with self.assertRaises(ValueError):
                env_float("BAD_FLOAT")
        finally:
            os.environ.clear()
            os.environ.update(old)

    def test_env_list(self) -> None:
        import os

        old = os.environ.copy()
        os.environ.update({"TAGS": "  web , api, backend  "})
        try:
            self.assertEqual(env_list("TAGS"), ["web", "api", "backend"])
            self.assertEqual(env_list("TAGS", strip=False), ["  web ", " api", " backend  "])
            self.assertEqual(env_list("MISSING_TAGS", default=["default"]), ["default"])
        finally:
            os.environ.clear()
            os.environ.update(old)


class TestParsingWave3(unittest.TestCase):
    def test_safe_int_base_and_bounds_validation(self) -> None:
        self.assertIsNone(safe_int("10", base=40))
        self.assertIsNone(safe_int("10", min=50, max=20))
        self.assertEqual(safe_int("1010", base=2), 10)

    def test_safe_float_bounds_and_zero(self) -> None:
        self.assertIsNone(safe_float("1.0", min=5.0, max=2.0))
        # -0.0 normalization
        val = safe_float("-0.0")
        self.assertEqual(val, 0.0)
        self.assertFalse(str(val).startswith("-"))

    def test_parse_bool_bytes_and_error(self) -> None:
        self.assertTrue(parse_bool(b"  true  "))
        self.assertFalse(parse_bool(bytearray(b"0")))
        with self.assertRaises(ValueError) as ctx:
            parse_bool("invalid_boolean_string")
        self.assertIn("Cannot parse bool from type str", str(ctx.exception))
        self.assertNotIn("invalid_boolean_string", str(ctx.exception))


class TestTypedConfigWave3(unittest.TestCase):
    def test_config_value_slots_and_source_validation(self) -> None:
        cv = ConfigValue(value=42, source="env")
        self.assertEqual(cv.value, 42)
        with self.assertRaises(ValueError):
            ConfigValue(value=42, source="   ")

    def test_convert_callable_validation(self) -> None:
        with self.assertRaises(TypeError):
            convert("123", "not_callable")  # type: ignore[arg-type]


class TestDeprecationWave3(unittest.IsolatedAsyncioTestCase):
    def test_deprecated_validation_and_pep702(self) -> None:
        with self.assertRaises(ValueError):
            deprecated("")
        with self.assertRaises(TypeError):
            deprecated("old")("not_callable")  # type: ignore[arg-type]

        @deprecated("use new_func instead")
        def old_func(x: int) -> int:
            return x + 1

        self.assertEqual(old_func.__deprecated__, "use new_func instead")
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            res = old_func(2)
            self.assertEqual(res, 3)
            self.assertEqual(len(recorded), 1)
            self.assertTrue(issubclass(recorded[0].category, GunzDeprecationWarning))

    async def test_deprecated_async_function(self) -> None:
        @deprecated("async func is old")
        async def old_async(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * 2

        self.assertEqual(old_async.__deprecated__, "async func is old")
        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            res = await old_async(3)
            self.assertEqual(res, 6)
            self.assertEqual(len(recorded), 1)
            self.assertTrue(issubclass(recorded[0].category, GunzDeprecationWarning))


class TestResultWave3(unittest.TestCase):
    def test_result_callable_validations(self) -> None:
        ok = Result.ok(10)
        err = Result.err("failed")

        with self.assertRaises(TypeError):
            ok.map("not_callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            err.map_error("not_callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            err.unwrap_or_else("not_callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            ok.and_then("not_callable")  # type: ignore[arg-type]

    def test_result_unwrap_err_and_unwrap_or_else(self) -> None:
        err = Result.err("not found")
        self.assertEqual(err.unwrap_err(), "not found")

        ok = Result.ok(42)
        with self.assertRaises(RuntimeError):
            ok.unwrap_err()

        self.assertEqual(ok.unwrap_or_else(lambda e: 0), 42)
        self.assertEqual(err.unwrap_or_else(lambda e: len(e)), 9)

    def test_result_and_then(self) -> None:
        def double_if_even(x: int) -> Result[int, str]:
            if x % 2 == 0:
                return Result.ok(x * 2)
            return Result.err("odd number")

        self.assertEqual(Result.ok(4).and_then(double_if_even).unwrap(), 8)
        self.assertEqual(Result.ok(3).and_then(double_if_even).unwrap_err(), "odd number")
        self.assertEqual(Result.err("initial").and_then(double_if_even).unwrap_err(), "initial")


class TestVersioningWave3(unittest.TestCase):
    def test_versioned_envelope_metadata_mapping_proxy(self) -> None:
        env = VersionedEnvelope(schema="user", version=1, payload={"name": "Alice"}, metadata={"tag": "v1"})
        self.assertIsInstance(env.metadata, MappingProxyType)
        with self.assertRaises(TypeError):
            env.metadata["tag"] = "v2"  # type: ignore[index]

    def test_schema_migrator_can_migrate_and_latest_version(self) -> None:
        migrator = SchemaMigrator()
        migrator.register("user", 1, lambda d: {**d, "version": 2})
        migrator.register("user", 2, lambda d: {**d, "version": 3})

        self.assertTrue(migrator.can_migrate("user", 1, target_version=3))
        self.assertFalse(migrator.can_migrate("user", 1, target_version=4))
        self.assertEqual(migrator.latest_version("user"), 3)
        self.assertIsNone(migrator.latest_version("unknown"))

        envelope = VersionedEnvelope(schema="user", version=1, payload={"name": "Alice"})
        migrated = migrator.migrate(envelope, target_version=3)
        self.assertEqual(migrated.version, 3)

    def test_schema_migrator_exception_propagation(self) -> None:
        migrator = SchemaMigrator()

        def broken_migration(payload):
            raise KeyError("missing required key")

        migrator.register("doc", 1, broken_migration)
        envelope = VersionedEnvelope(schema="doc", version=1, payload={})
        with self.assertRaises(KeyError) as ctx:
            migrator.migrate(envelope, target_version=2)
        self.assertIn("missing required key", str(ctx.exception))


class TestIdentifiersWave3(unittest.TestCase):
    def test_short_id_bytes(self) -> None:
        from_str = short_id("hello world")
        from_bytes = short_id(b"hello world")
        self.assertEqual(from_str, from_bytes)

    def test_is_valid_uuid(self) -> None:
        import uuid

        u4 = str(uuid.uuid4())
        u5 = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://example.com"))

        self.assertTrue(is_valid_uuid(u4))
        self.assertTrue(is_valid_uuid(u4, version=4))
        self.assertFalse(is_valid_uuid(u4, version=5))

        self.assertTrue(is_valid_uuid(u5, version=5))
        self.assertFalse(is_valid_uuid("not-a-uuid"))
        self.assertFalse(is_valid_uuid(12345))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
