from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gunz_utils.benchmark.artifacts import register_artifact
from gunz_utils.benchmark.performance import PerformanceRun
from gunz_utils.benchmark.protocol import WorkerRequest
from gunz_utils.benchmark.result import SystemInfo


class TestReproducibleRuns(unittest.TestCase):
    def test_worker_request_is_versioned(self) -> None:
        request = WorkerRequest("example", ("--size", "10"), seed=42)
        data = request.to_dict()
        self.assertEqual(data["protocol_version"], 1)
        json.dumps(data)

    def test_artifact_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.txt"
            path.write_text("payload", encoding="utf-8")
            run = PerformanceRun("demo", SystemInfo.capture())
            updated = register_artifact(run, path, kind="profile")
        artifact = updated.artifacts[0]
        self.assertEqual(len(artifact.checksum_sha256 or ""), 64)
        self.assertEqual(artifact.size_bytes, 7)


if __name__ == "__main__":
    unittest.main()
