from __future__ import annotations

import pathlib
import tempfile
import unittest
from unittest.mock import patch

from gunz_utils import atomic_write


class TestAtomicWrite(unittest.TestCase):
    def test_basic_text_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.txt"
            atomic_write(path, "hello")
            self.assertEqual(path.read_text(), "hello")

    def test_binary_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.bin"
            atomic_write(path, b"\x00\x01", mode="wb")
            self.assertEqual(path.read_bytes(), b"\x00\x01")

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.txt"
            path.write_text("old")
            atomic_write(path, "new")
            self.assertEqual(path.read_text(), "new")

    def test_mkdir_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "nested" / "test.txt"
            atomic_write(path, "hello", mkdir=True)
            self.assertEqual(path.read_text(), "hello")

    def test_missing_parent_raises_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "missing" / "test.txt"
            with self.assertRaises(FileNotFoundError):
                atomic_write(path, "hello")

    def test_binary_mode_rejects_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.bin"
            with self.assertRaises(ValueError):
                atomic_write(path, "text", mode="wb")

    def test_text_mode_rejects_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.txt"
            with self.assertRaises(ValueError):
                atomic_write(path, b"bytes")

    def test_encoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.txt"
            atomic_write(path, "Hello, 世界", encoding="utf-8")
            self.assertEqual(path.read_bytes(), "Hello, 世界".encode())

    def test_replace_failure_cleans_temp_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.txt"
            path.write_text("old")
            with patch("gunz_utils.io.os.replace", side_effect=OSError("failure")):
                with self.assertRaises(OSError):
                    atomic_write(path, "new")
            self.assertEqual(path.read_text(), "old")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_success_cleans_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "test.txt"
            atomic_write(path, "new")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
