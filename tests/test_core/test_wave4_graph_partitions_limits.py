"""Tests for Wave 4: Provenance Graph, Partitions, Sampling, Limits, and Resources."""

from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest

from gunz_utils.faults import FailAfter, FaultSequence
from gunz_utils.instrumentation import Counter, Timer
from gunz_utils.limits import BudgetExceededError, Limits, ResourceBudget
from gunz_utils.partitions import (
    PartitionManifest,
    assert_disjoint_partitions,
    partition_overlaps,
)
from gunz_utils.provenance_graph import ProvenanceGraph, ProvenanceNode
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup
from gunz_utils.sampling import sample_named_items, stable_priority


class TestProvenanceGraphWave4(unittest.TestCase):
    def test_generator_inputs_not_exhausted(self) -> None:
        def gen():
            yield "p1"
            yield "p2"

        node = ProvenanceNode(identifier="child", kind="artifact", inputs=gen())  # type: ignore[arg-type]
        self.assertEqual(node.inputs, ("p1", "p2"))

    def test_add_validation_and_descendants_topo_order(self) -> None:
        graph = ProvenanceGraph()
        with self.assertRaises(TypeError):
            graph.add("not_a_node")  # type: ignore[arg-type]

        n1 = ProvenanceNode("root", "dataset")
        n2 = ProvenanceNode("intermediate", "model", inputs=("root",))
        n3 = ProvenanceNode("leaf", "metric", inputs=("intermediate",))

        graph.add(n1)
        graph.add(n2)
        graph.add(n3)

        self.assertEqual(graph.descendants("root"), ("intermediate", "leaf"))
        self.assertEqual(graph.descendants("intermediate"), ("leaf",))
        self.assertEqual(graph.descendants("leaf"), ())

        topo = graph.topological_order()
        self.assertEqual([n.identifier for n in topo], ["root", "intermediate", "leaf"])

    def test_cycle_detection(self) -> None:
        graph = ProvenanceGraph()
        n1 = ProvenanceNode("a", "step", inputs=("b",))
        n2 = ProvenanceNode("b", "step", inputs=("a",))
        graph.add(n1)
        with self.assertRaises(ValueError) as ctx:
            graph.add(n2)
        self.assertIn("cycle detected", str(ctx.exception))


class TestPartitionsWave4(unittest.TestCase):
    def test_whitespace_items_rejected(self) -> None:
        with self.assertRaises(ValueError):
            PartitionManifest({"p1": ["valid", "   "]})

    def test_partition_manifest_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "partitions.json"
            manifest = PartitionManifest({"train": ["img1", "img2"], "val": ["img3"]})
            manifest.write(file_path)

            loaded = PartitionManifest.load(file_path)
            self.assertEqual(loaded.fingerprint, manifest.fingerprint)
            self.assertEqual(loaded.partitions["train"], ("img1", "img2"))

            # Corrupt the fingerprint
            corrupted = file_path.read_text().replace(manifest.fingerprint, "corrupted_fp")
            file_path.write_text(corrupted)
            with self.assertRaises(ValueError) as ctx:
                PartitionManifest.load(file_path)
            self.assertIn("fingerprint mismatch", str(ctx.exception))

    def test_partition_overlaps_rejects_bare_strings(self) -> None:
        with self.assertRaises(TypeError):
            partition_overlaps({"p1": "bare_string"})  # type: ignore[arg-type]


class TestSamplingWave4(unittest.TestCase):
    def test_sample_named_items_patterns_and_zero_limit(self) -> None:
        items = [("apple", 1), ("banana", 2), ("apricot", 3)]
        with self.assertRaises(TypeError):
            sample_named_items(items, limit=2, include_patterns="app*")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            sample_named_items(items, limit=2, exclude_patterns="app*")  # type: ignore[arg-type]

        self.assertEqual(sample_named_items(items, limit=0), [])
        sampled = sample_named_items(items, limit=2, include_patterns=("ap*",))
        self.assertEqual(len(sampled), 2)
        self.assertTrue(all(name.startswith("ap") for name, _ in sampled))


class TestLimitsWave4(unittest.TestCase):
    def test_limits_check_and_depth(self) -> None:
        limits = Limits(max_bytes=100, max_items=10, max_steps=5, max_depth=3)
        limits.check_bytes(50)
        limits.check_items(5)
        limits.check_steps(2)
        limits.check_depth(2)

        with self.assertRaises(BudgetExceededError):
            limits.check_bytes(101)
        with self.assertRaises(BudgetExceededError):
            limits.check_items(11)
        with self.assertRaises(BudgetExceededError):
            limits.check_steps(6)
        with self.assertRaises(BudgetExceededError):
            limits.check_depth(4)

    def test_resource_budget_from_limits_and_snapshot(self) -> None:
        with self.assertRaises(TypeError):
            ResourceBudget.from_limits("not_limits")  # type: ignore[arg-type]

        limits = Limits(max_bytes=500, max_items=20)
        budget = ResourceBudget.from_limits(limits)
        budget.consume_bytes(100)
        budget.consume_items(5)

        snap = budget.snapshot()
        self.assertEqual(snap["bytes_used"], 100)
        self.assertEqual(snap["max_bytes"], 500)
        self.assertEqual(snap["items_used"], 5)
        self.assertEqual(snap["max_items"], 20)


class TestResourcesWave4(unittest.IsolatedAsyncioTestCase):
    def test_resource_group_callback_and_close(self) -> None:
        events: list[str] = []
        rg = ResourceGroup()
        rg.callback(lambda: events.append("cleaned"))
        self.assertEqual(events, [])
        rg.close()
        self.assertEqual(events, ["cleaned"])

    async def test_async_resource_group_callback_and_aclose(self) -> None:
        events: list[str] = []
        arg = AsyncResourceGroup()
        arg.callback(lambda: events.append("async_cleaned"))
        self.assertEqual(events, [])
        await arg.aclose()
        self.assertEqual(events, ["async_cleaned"])


class TestInstrumentationWave4(unittest.TestCase):
    def test_counter_reset(self) -> None:
        c = Counter()
        c.add(10)
        self.assertEqual(c.value, 10)
        prev = c.reset()
        self.assertEqual(prev, 10)
        self.assertEqual(c.value, 0)

    def test_timer_validation_and_reset(self) -> None:
        with self.assertRaises(ValueError):
            Timer("   ")

        timer = Timer("op")
        with timer:
            pass
        self.assertIsNotNone(timer.result)
        timer.reset()
        self.assertIsNone(timer.result)
        self.assertEqual(timer.started, 0.0)


if __name__ == "__main__":
    unittest.main()
