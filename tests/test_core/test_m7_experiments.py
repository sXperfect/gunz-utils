from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import gunz_utils.benchmark as api
from gunz_utils.benchmark import (
    PerformanceRun,
    SystemInfo,
    register_artifact,
    run_experiment,
    save_run_directory,
)


class TestM7Experiments(unittest.TestCase):
    def test_cartesian_repetitions(self) -> None:
        def work(*, a: int, b: int) -> int:
            return a + b

        results = run_experiment(
            work,
            parameters={"a": [1, 2], "b": [10, 20]},
            repetitions=2,
            warmup=0,
            iterations=1,
        )
        self.assertEqual(len(results), 8)

    def test_repetitions_reject_boolean_and_nonpositive_values(self) -> None:
        def work(*, a: int) -> int:
            return a

        for value in (True, 0, -1):
            with self.subTest(repetitions=value):
                with self.assertRaises(ValueError):
                    run_experiment(
                        work,
                        parameters={"a": [1]},
                        repetitions=value,
                        warmup=0,
                        iterations=1,
                    )

    def test_self_contained_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "profile.txt"
            source.write_text("profile", encoding="utf-8")
            run = register_artifact(
                PerformanceRun("demo", SystemInfo.capture()),
                source,
                kind="profile",
            )
            target = Path(directory) / "run"
            packaged = save_run_directory(run, target)
            self.assertTrue((target / "run.json").exists())
            self.assertTrue(Path(packaged.artifacts[0].path).exists())

    def test_benchmark_package_contract(self) -> None:
        missing = [name for name in api.__all__ if not hasattr(api, name)]
        self.assertEqual(missing, [])
        self.assertEqual(len(api.__all__), len(set(api.__all__)))


if __name__ == "__main__":
    unittest.main()
