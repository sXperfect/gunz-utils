from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from gunz_utils.limits import BudgetExceededError, Limits, ResourceBudget
from gunz_utils.plugins import discover_plugins
from gunz_utils.provenance import capture_runtime_provenance
from gunz_utils.versioning import (
    SchemaMigrationError,
    SchemaMigrator,
    VersionedEnvelope,
)


class FakeEntryPoint:
    def __init__(self, name: str, value: str, loaded: object) -> None:
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self) -> object:
        if isinstance(self._loaded, BaseException):
            raise self._loaded
        return self._loaded


class TestPlugins(unittest.TestCase):
    def test_discovery_is_deterministic_and_failure_isolated(self) -> None:
        entries = [
            FakeEntryPoint("zeta", "z:plugin", RuntimeError("boom")),
            FakeEntryPoint("alpha", "a:plugin", object()),
        ]
        with patch("gunz_utils.plugins.entry_points", return_value=entries):
            results = discover_plugins("demo.plugins")
        self.assertEqual([item.info.name for item in results], ["alpha", "zeta"])
        self.assertTrue(results[0].ok)
        self.assertFalse(results[1].ok)
        self.assertIn("RuntimeError", results[1].error or "")

    def test_instantiation_requires_callable_plugin(self) -> None:
        entries = [FakeEntryPoint("bad", "bad:plugin", object())]
        with patch("gunz_utils.plugins.entry_points", return_value=entries):
            result = discover_plugins("demo.plugins", instantiate=True)[0]
        self.assertFalse(result.ok)
        self.assertIn("TypeError", result.error or "")


class TestResourceBudget(unittest.TestCase):
    def test_consumption_and_remaining_values(self) -> None:
        now = [10.0]
        budget = ResourceBudget(
            max_bytes=10,
            max_items=2,
            max_depth=3,
            timeout=5,
            clock=lambda: now[0],
        )
        self.assertEqual(budget.consume_bytes(4), 4)
        self.assertEqual(budget.remaining_bytes, 6)
        self.assertEqual(budget.consume_items(), 1)
        budget.check_depth(3)
        now[0] = 14.0
        budget.check_deadline()
        self.assertEqual(budget.remaining_seconds, 1.0)

    def test_budget_rejects_overages_without_consuming(self) -> None:
        budget = ResourceBudget(max_bytes=3, max_items=1, max_depth=1)
        with self.assertRaises(BudgetExceededError):
            budget.consume_bytes(4)
        self.assertEqual(budget.bytes_used, 0)
        budget.consume_items()
        with self.assertRaises(BudgetExceededError):
            budget.consume_items()
        self.assertEqual(budget.items_used, 1)
        with self.assertRaises(BudgetExceededError):
            budget.check_depth(2)

    def test_deadline_uses_injected_monotonic_clock(self) -> None:
        now = [1.0]
        budget = ResourceBudget(timeout=2, clock=lambda: now[0])
        now[0] = 3.1
        with self.assertRaises(BudgetExceededError):
            budget.check_deadline()

    def test_from_limits(self) -> None:
        budget = ResourceBudget.from_limits(Limits(max_bytes=7, max_items=4))
        self.assertEqual(budget.remaining_bytes, 7)
        self.assertEqual(budget.remaining_items, 4)


class TestProvenance(unittest.TestCase):
    def test_environment_requires_explicit_allowlist(self) -> None:
        with patch.dict(os.environ, {"VISIBLE_FOR_TEST": "yes", "SECRET_FOR_TEST": "no"}):
            result = capture_runtime_provenance(
                environment_allowlist=["VISIBLE_FOR_TEST", "MISSING_FOR_TEST"]
            )
        self.assertEqual(result.environment, {"VISIBLE_FOR_TEST": "yes"})
        self.assertNotIn("SECRET_FOR_TEST", result.environment)
        self.assertTrue(result.python_version)


class TestVersioning(unittest.TestCase):
    def test_envelope_round_trip(self) -> None:
        envelope = VersionedEnvelope("demo", 1, {"value": 2}, {"source": "test"})
        self.assertEqual(VersionedEnvelope.from_dict(envelope.to_dict()), envelope)

    def test_forward_migration_chain(self) -> None:
        migrator = SchemaMigrator()
        migrator.register("demo", 1, lambda payload: {**payload, "v2": True})
        migrator.register("demo", 2, lambda payload: {**payload, "v3": True})
        result = migrator.migrate(
            VersionedEnvelope("demo", 1, {"value": 1}),
            target_version=3,
        )
        self.assertEqual(result.version, 3)
        self.assertTrue(result.payload["v2"])
        self.assertTrue(result.payload["v3"])

    def test_missing_migration_and_downgrade_fail(self) -> None:
        migrator = SchemaMigrator()
        envelope = VersionedEnvelope("demo", 2, {})
        with self.assertRaises(SchemaMigrationError):
            migrator.migrate(envelope, target_version=1)
        with self.assertRaises(SchemaMigrationError):
            migrator.migrate(envelope, target_version=3)

    def test_from_dict_validates_types(self) -> None:
        with self.assertRaises(SchemaMigrationError):
            VersionedEnvelope.from_dict(
                {"schema": "demo", "version": True, "payload": {}}
            )


if __name__ == "__main__":
    unittest.main()
