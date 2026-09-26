from __future__ import annotations

import gc
import json
import unittest

from gunz_utils.benchmark import (
    BenchmarkSuite,
    PerformanceArtifact,
    PerformanceRun,
    SystemInfo,
    benchmark,
    benchmark_environment,
    run_python_worker,
    worker_json,
)


class TestExecutionControls(unittest.TestCase):
    def test_gc_restored(self) -> None:
        before = gc.isenabled()
        with benchmark_environment(disable_gc=True):
            self.assertFalse(gc.isenabled())
        self.assertEqual(gc.isenabled(), before)

    def test_adaptive_sampling(self) -> None:
        result = benchmark(
            lambda: None,
            warmup=0,
            iterations=2,
            min_time=0.001,
            max_iterations=20,
            target_time=0.0001,
        )
        self.assertGreaterEqual(result.iterations, 2)

    def test_parameter_sweep(self) -> None:
        def work(*, size: int) -> int:
            return sum(range(size))

        suite = BenchmarkSuite("sweep")
        suite.add_parameters("sum", work, "size", [1, 10])
        results = suite.run(warmup=0, iterations=1)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].parameters["size"], 1)


class TestPerformanceRun(unittest.TestCase):
    def test_serializable(self) -> None:
        run = PerformanceRun(
            name="demo",
            system=SystemInfo.capture(),
            artifacts=(PerformanceArtifact("profile", "perf.data"),),
            metrics={"throughput": 42.0},
        )
        json.dumps(run.to_dict())


class TestWorker(unittest.TestCase):
    def test_worker_process(self) -> None:
        result = run_python_worker(
            "json.tool",
            args=(),
        )
        self.assertNotEqual(result.returncode, 0)

    def test_worker_json(self) -> None:
        self.assertEqual(
            worker_json(type("R", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()),
            {},
        )


if __name__ == "__main__":
    unittest.main()
