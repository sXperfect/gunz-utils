from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

from gunz_utils.benchmark import profile_command, save_process_csv


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux /proc required")
class TestDeepProcessProfile(unittest.TestCase):
    def test_lineage_and_extended_metrics(self) -> None:
        profile = profile_command(
            [
                sys.executable,
                "-c",
                "import subprocess,sys,time;"
                "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(.03)']);"
                "time.sleep(.02);p.wait()",
            ],
            interval=0.002,
            check=True,
        )
        self.assertGreaterEqual(profile.peak_process_count, 1)
        self.assertGreaterEqual(profile.peak_threads, 1)
        self.assertGreaterEqual(profile.peak_rss_bytes, 0)
        self.assertTrue(any(sample.processes for sample in profile.samples))
        details = [p for sample in profile.samples for p in sample.processes]
        self.assertTrue(all(detail.pid > 0 for detail in details))

    def test_csv_export(self) -> None:
        profile = profile_command(
            [sys.executable, "-c", "sum(range(10000))"],
            interval=0.001,
            check=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.csv"
            save_process_csv(profile, path)
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertGreaterEqual(len(rows), 1)
        self.assertIn("rss_bytes", rows[0])
        self.assertIn("pss_bytes", rows[0])


if __name__ == "__main__":
    unittest.main()
