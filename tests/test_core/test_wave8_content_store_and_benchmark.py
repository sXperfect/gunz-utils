"""Tests for Wave 8: content store and benchmarking suite (#93–#100)."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.benchmark.artifacts import register_artifact, verify_artifact
from gunz_utils.benchmark.export import save_process_csv
from gunz_utils.benchmark.process import ProcessProfile, ProcessSample
from gunz_utils.benchmark.report import format_comparison, format_process_profile
from gunz_utils.benchmark.result import BenchmarkResult, BenchmarkStats, SystemInfo
from gunz_utils.benchmark.runner import (
    benchmark,
    benchmark_environment,
    calibrate_loops,
)
from gunz_utils.benchmark.suite import BenchmarkCase, BenchmarkSuite
from gunz_utils.content_store import ContentAddressedStore, StoredArtifact


class TestWave8ContentStore(unittest.TestCase):
    def test_item93_read_bytes_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContentAddressedStore(Path(tmpdir))
            art = store.put_bytes(b"hello content store")
            #? Successful read
            data = store.read_bytes(art.digest)
            self.assertEqual(data, b"hello content store")

            #? max_bytes bound check
            with self.assertRaises(ValueError):
                store.read_bytes(art.digest, max_bytes=5)

    def test_item94_delete_stored_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContentAddressedStore(Path(tmpdir))
            art = store.put_bytes(b"temp data")
            self.assertTrue(store.verify(art.digest))

            #? Delete existing
            self.assertTrue(store.delete(art.digest))
            self.assertFalse(store.verify(art.digest))

            #? Delete non-existent returns False
            self.assertFalse(store.delete(art.digest))

    def test_item95_stored_artifact_post_init_validation(self) -> None:
        with self.assertRaises(ValueError):
            StoredArtifact(digest="", path=Path("/tmp"), size_bytes=10)
        with self.assertRaises(ValueError):
            StoredArtifact(digest="abc", path=Path("/tmp"), size_bytes=-1)
        with self.assertRaises(ValueError):
            StoredArtifact(digest="abc", path=Path("/tmp"), size_bytes=True)  # type: ignore[arg-type]

        art = StoredArtifact(digest="sha256:123", path=Path("/tmp/foo"), size_bytes=100)
        self.assertEqual(art.digest, "sha256:123")
        self.assertEqual(art.size_bytes, 100)


class TestWave8Benchmark(unittest.TestCase):
    def test_item96_save_process_csv_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_csv = Path(tmpdir) / "profile.csv"
            sample = ProcessSample(
                elapsed=0.1,
                process_count=1,
                threads=1,
                cpu_user_seconds=0.05,
                cpu_system_seconds=0.01,
                rss_bytes=1024,
                pss_bytes=1024,
                private_bytes=1024,
                read_bytes=0,
                write_bytes=0,
                minor_faults=0,
                major_faults=0,
                voluntary_context_switches=0,
                involuntary_context_switches=0,
                processes=(),
            )
            profile = ProcessProfile(
                args=("echo", "hi"),
                returncode=0,
                wall_seconds=0.1,
                cpu_user_seconds=0.05,
                cpu_system_seconds=0.01,
                peak_rss_bytes=1024,
                peak_pss_bytes=1024,
                peak_private_bytes=1024,
                peak_process_count=1,
                peak_threads=1,
                read_bytes=0,
                write_bytes=0,
                minor_faults=0,
                major_faults=0,
                voluntary_context_switches=0,
                involuntary_context_switches=0,
                samples=(sample,),
            )
            save_process_csv(profile, out_csv)
            self.assertTrue(out_csv.exists())
            content = out_csv.read_text(encoding="utf-8")
            self.assertIn("elapsed", content)
            self.assertIn("rss_bytes", content)

    def test_item97_runner_validations(self) -> None:
        with self.assertRaises(TypeError):
            benchmark("not-a-callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            calibrate_loops("not-a-callable")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            with benchmark_environment(disable_gc="no"):  # type: ignore[arg-type]
                pass
        with self.assertRaises(TypeError):
            with benchmark_environment(cpu_affinity="not-a-set"):  # type: ignore[arg-type]
                pass

    def test_item98_benchmark_suite_and_case(self) -> None:
        with self.assertRaises(ValueError):
            BenchmarkCase(name="", func=lambda: None)
        with self.assertRaises(TypeError):
            BenchmarkCase(name="valid", func="not-callable")  # type: ignore[arg-type]

        with self.assertRaises(ValueError):
            BenchmarkSuite(name="")
        suite = BenchmarkSuite("my_suite")
        with self.assertRaises(TypeError):
            suite.add("case1", "not-callable")  # type: ignore[arg-type]
        suite.add("case1", lambda: 1 + 1)
        self.assertEqual(len(suite._cases), 1)

    def test_item99_benchmark_result_slots_and_types(self) -> None:
        sys_info = SystemInfo.capture()
        self.assertTrue(hasattr(sys_info, "__slots__"))

        stats = BenchmarkStats(
            minimum=0.001,
            median=0.002,
            mean=0.002,
            p95=0.003,
            p99=0.004,
            maximum=0.005,
            stddev=0.0001,
            ops_per_second=500.0,
        )
        self.assertTrue(hasattr(stats, "__slots__"))
        with self.assertRaises(TypeError):
            BenchmarkStats(
                minimum="bad",  # type: ignore[arg-type]
                median=0.002,
                mean=0.002,
                p95=0.003,
                p99=0.004,
                maximum=0.005,
                stddev=0.0001,
                ops_per_second=500.0,
            )

        res = BenchmarkResult(
            name="case_a",
            samples=(0.001, 0.002),
            stats=stats,
            warmup=1,
            iterations=2,
            system=sys_info,
        )
        self.assertTrue(hasattr(res, "__slots__"))

    def test_item100_report_and_artifact_type_validations(self) -> None:
        with self.assertRaises(TypeError):
            format_comparison("not-a-comparison")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            format_process_profile("not-a-profile")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            register_artifact("not-a-run", Path("/tmp/foo"), kind="log")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            verify_artifact("not-an-artifact")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
