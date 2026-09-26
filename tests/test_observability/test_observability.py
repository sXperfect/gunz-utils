"""Tests for the optional Loguru observability backend."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gunz_utils import setup_logging


class TestSetupLogging(unittest.TestCase):
    def test_console_only_setup(self) -> None:
        setup_logging("test-console", verbose=False)

    def test_file_setup_creates_log_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup_logging("test-file", verbose=True, project_root=root)
            self.assertTrue((root / "logs").is_dir())


if __name__ == "__main__":
    unittest.main()
