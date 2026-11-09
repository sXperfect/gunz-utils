"""Tests for Wave 6: Benchmark Subpackage Correctness, Safety & Performance."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from gunz_utils.benchmark.compare import compare_results
from gunz_utils.benchmark.diagnostics import analyze_stability
from gunz_utils.benchmark.gate import evaluate_regression_gate
from gunz_utils.benchmark.history import BenchmarkHistory, HistoryPoint
from gunz_utils.benchmark.io import capture_git_info, save_result
from gunz_utils.benchmark.perf import perf_record, perf_stat
from gunz_utils.benchmark.performance import PerformanceRun
from gunz_utils.benchmark.plot import plot_benchmark, plot_history
from gunz_utils.benchmark.policy import MetricPolicy
from gunz_utils.benchmark.protocol import WorkerRequest, WorkerResponse
from gunz_utils.benchmark.result import BenchmarkResult, BenchmarkStats, SystemInfo
from gunz_utils.benchmark.run_directory import load_run_directory, save_run_directory
from gunz_utils.benchmark.safe_io import load_result_checked
from gunz_utils.benchmark.schema import PerformanceSchemaError, validate_performance_run
from gunz_utils.benchmark.trends import summarize_history
from gunz_utils.benchmark.worker import run_python_worker


def _make_dummy_result(name: str = "test_bench") -> BenchmarkResult:
    stats = BenchmarkStats(
        minimum=0.01,
        median=0.02,
        mean=0.02,
        p95=0.03,
        p99=0.04,
        maximum=0.05,
        stddev=0.005,
        ops_per_second=50.0,
    )
    system = SystemInfo(
        python="3.11",
        platform="Linux",
        machine="x86_64",
        processor="x86_64",
        cpu_count=8,
    )
    return BenchmarkResult(
        name=name,
        samples=(0.01, 0.02, 0.05),
        stats=stats,
        warmup=1,
        iterations=3,
        system=system,
    )


class TestBenchmarkWave6(unittest.TestCase):
    def test_save_result_and_load_checked(self) -> None:
        result = _make_dummy_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "result.json"
            save_result(result, file_path)
            self.assertTrue(file_path.is_file())

            loaded = load_result_checked(file_path)
            self.assertEqual(loaded.name, result.name)
            self.assertEqual(loaded.stats.median, 0.02)

    def test_load_result_rejects_non_regular_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError) as ctx:
                load_result_checked(tmpdir)
            self.assertIn("regular file", str(ctx.exception))

    def test_load_result_rejects_nan_json(self) -> None:
        result = _make_dummy_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "corrupt.json"
            data = result.to_dict()
            content = json.dumps(data).replace("0.02", "NaN")
            file_path.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_result_checked(file_path)
            self.assertIn("non-standard JSON constant", str(ctx.exception))

    def test_load_result_validates_stats_invariants(self) -> None:
        result = _make_dummy_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "bad_stats.json"
            data = result.to_dict()
            # Violate minimum <= median <= maximum: set minimum > maximum
            data["stats"]["minimum"] = 1.0
            file_path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                load_result_checked(file_path)
            self.assertIn("ordering invariant violated", str(ctx.exception))

    def test_perf_validations(self) -> None:
        with self.assertRaises(TypeError):
            perf_stat("ls -l")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            perf_record("ls -l", "out.data")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            perf_record(["ls"], "-rf")

    def test_plot_eager_type_validation(self) -> None:
        with self.assertRaises(TypeError):
            plot_benchmark("not_a_result")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            plot_history("not_a_history")  # type: ignore[arg-type]

    def test_gate_and_policy_validation(self) -> None:
        policy = MetricPolicy(name="median", direction="lower", relative_threshold=0.1)
        with self.assertRaises(TypeError):
            evaluate_regression_gate("not_mapping", {}, (policy,))  # type: ignore[arg-type]

    def test_protocol_worker_request_from_dict_and_slots(self) -> None:
        req = WorkerRequest(module="sys", arguments=("arg1",))
        d = req.to_dict()
        req2 = WorkerRequest.from_dict(d)
        self.assertEqual(req, req2)

        resp = WorkerResponse(returncode=0, payload={"ok": True})
        resp2 = WorkerResponse.from_dict(resp.to_dict())
        self.assertEqual(resp, resp2)

    def test_run_python_worker_module_identifier_validation(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            run_python_worker("bad module with spaces")
        self.assertIn("valid Python module name", str(ctx.exception))

    def test_trends_and_fsum(self) -> None:
        res1 = _make_dummy_result("run1")
        res2 = _make_dummy_result("run2")
        history = BenchmarkHistory([HistoryPoint("v1", res1), HistoryPoint("v2", res2)])

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].label, "v1")
        self.assertEqual([p.label for p in history], ["v1", "v2"])

        summary = summarize_history(history, metric="median")
        self.assertEqual(summary.metric, "median")
        self.assertEqual(summary.slope_per_step, 0.0)

    def test_schema_validation(self) -> None:
        with self.assertRaises(PerformanceSchemaError):
            validate_performance_run("not_a_mapping")  # type: ignore[arg-type]

    def test_run_directory_roundtrip(self) -> None:
        system = SystemInfo("3.11", "Linux", "x86_64", "x86_64", 4)
        run = PerformanceRun(name="bench_test", system=system)
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "perf_run"
            save_run_directory(run, run_dir)
            loaded = load_run_directory(run_dir)
            self.assertEqual(loaded.name, "bench_test")
            self.assertEqual(loaded.system.python, "3.11")

    def test_compare_and_diagnostics_validation(self) -> None:
        with self.assertRaises(TypeError):
            compare_results("not_res1", "not_res2")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            analyze_stability("not_result")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
