from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import gunz_utils.benchmark as benchmark_api
from gunz_utils.benchmark import (
    MetricPolicy,
    PerformanceRun,
    SystemInfo,
    evaluate_regression_gate,
    migrate_performance_run,
    register_artifact,
    validate_performance_run,
    verify_artifact,
)


class TestM6ProductionHardening(unittest.TestCase):
    def test_benchmark_public_api_resolves(self) -> None:
        missing = [
            name
            for name in benchmark_api.__all__
            if not hasattr(benchmark_api, name)
        ]
        self.assertEqual(missing, [])
        self.assertEqual(
            len(benchmark_api.__all__),
            len(set(benchmark_api.__all__)),
        )

    def test_schema_validation_and_migration(self) -> None:
        run = PerformanceRun("demo", SystemInfo.capture())
        data = run.to_dict()
        validate_performance_run(data)
        migrated = migrate_performance_run(data)
        self.assertEqual(migrated["schema_version"], 1)

    def test_schema_rejects_boolean_version(self) -> None:
        run = PerformanceRun("demo", SystemInfo.capture())
        data = run.to_dict()
        data["schema_version"] = True
        with self.assertRaises(ValueError):
            validate_performance_run(data)
        with self.assertRaises(ValueError):
            migrate_performance_run(data)

    def test_artifact_integrity_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.bin"
            path.write_bytes(b"original")
            run = register_artifact(
                PerformanceRun("demo", SystemInfo.capture()),
                path,
                kind="profile",
            )
            artifact = run.artifacts[0]
            self.assertTrue(verify_artifact(artifact))
            path.write_bytes(b"tampered")
            self.assertFalse(verify_artifact(artifact))

    def test_artifact_registry_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target.bin"
            target.write_bytes(b"secret")
            link = root / "artifact.bin"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "symlink"):
                register_artifact(
                    PerformanceRun("demo", SystemInfo.capture()),
                    link,
                    kind="profile",
                )

    def test_regression_gate_respects_comparability(self) -> None:
        policy = MetricPolicy(
            "latency",
            "lower",
            relative_threshold=0.05,
        )
        good = evaluate_regression_gate(
            {"latency": 1.0},
            {"latency": 1.01},
            (policy,),
        )
        self.assertTrue(good.passed)
        noisy = evaluate_regression_gate(
            {"latency": 1.0},
            {"latency": 1.01},
            (policy,),
            warnings=("processor differs",),
        )
        self.assertFalse(noisy.passed)


if __name__ == "__main__":
    unittest.main()
