"""Tests for the optional Loguru observability backend."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch
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

    def test_log_name_cannot_escape_log_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("../escape", "nested/name", "..", ""):
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        setup_logging(name, project_root=root)
            self.assertFalse((root / "escape.log").exists())

    def test_session_id_is_not_interpreted_as_format_template(self) -> None:
        malicious = "{message}\n\x1b[31mINJECT"
        with patch.dict(os.environ, {"HH_SESSION_ID": malicious}):
            setup_logging("safe-session")


if __name__ == "__main__":
    unittest.main()
