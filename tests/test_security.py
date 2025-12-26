# -*- coding: utf-8 -*-
import unittest
import os
import tempfile
import shutil
from gunz_utils.security import sanitize_filename, safe_path_join

class TestSecurity(unittest.TestCase):
    def test_sanitize_filename_valid(self):
        """Test standard valid filenames."""
        self.assertEqual(sanitize_filename("test_file.txt"), "test_file.txt")
        self.assertEqual(sanitize_filename("image-123.png"), "image-123.png")
        self.assertEqual(sanitize_filename("MyFile.JPG"), "MyFile.JPG")

    def test_sanitize_filename_path_traversal(self):
        """Test protection against path traversal."""
        # os.path.basename handles the slashes, our regex handles the rest
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")

        # ".." -> basename ".." -> strip dots -> empty -> ValueError
        with self.assertRaisesRegex(ValueError, "Filename is empty"):
            sanitize_filename("..")

        with self.assertRaisesRegex(ValueError, "Filename is empty"):
            sanitize_filename(".")

    def test_sanitize_filename_dangerous_chars(self):
        """Test removal of dangerous characters."""
        # ? -> _
        # * -> _
        # file?name*.txt -> file_name_.txt
        self.assertEqual(sanitize_filename("file?name*.txt"), "file_name_.txt")
        self.assertEqual(sanitize_filename("file<name>.txt"), "file_name_.txt")
        self.assertEqual(sanitize_filename("file|name.txt"), "file_name.txt")
        self.assertEqual(sanitize_filename("file:name.txt"), "file_name.txt")

    def test_sanitize_filename_spaces(self):
        """Test handling of spaces."""
        self.assertEqual(sanitize_filename("my file name.txt"), "my_file_name.txt")
        self.assertEqual(sanitize_filename("my   file.txt"), "my_file.txt")

    def test_sanitize_filename_strip(self):
        """Test stripping of dots and replacements."""
        self.assertEqual(sanitize_filename(".hidden"), "hidden")
        self.assertEqual(sanitize_filename("_start"), "start")
        self.assertEqual(sanitize_filename("end_"), "end")
        self.assertEqual(sanitize_filename("file."), "file")

    def test_sanitize_filename_empty(self):
        """Test empty input."""
        with self.assertRaises(ValueError):
            sanitize_filename("")
        with self.assertRaises(ValueError):
            sanitize_filename("   ")
        with self.assertRaises(ValueError):
            sanitize_filename("///")

    def test_sanitize_filename_length(self):
        """Test length truncation."""
        long_name = "a" * 300
        sanitized = sanitize_filename(long_name)
        self.assertEqual(len(sanitized), 255)
        self.assertEqual(sanitized, "a" * 255)

    def test_sanitize_filename_windows_reserved(self):
        """Test handling of Windows reserved filenames."""
        reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved:
            # Should now be prefixed with underscore
            self.assertEqual(sanitize_filename(name), f"_{name}")
            self.assertEqual(sanitize_filename(f"{name}.txt"), f"_{name}.txt")
            self.assertEqual(sanitize_filename(f"{name}.tar.gz"), f"_{name}.tar.gz")

            # Case insensitive check
            self.assertEqual(sanitize_filename(name.lower()), f"_{name.lower()}")

    def test_sanitize_filename_unsafe_replacement(self):
        """Test that sanitize_filename rejects unsafe replacement characters."""
        unsafe_replacements = ["/", "\\", "foo/bar", "foo\\bar"]

        for replacement in unsafe_replacements:
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(ValueError, "Replacement string contains path separators"):
                    sanitize_filename("file*name.txt", replacement=replacement)

    def test_safe_path_join_valid(self):
        """Test valid path joins."""
        with tempfile.TemporaryDirectory() as tmp_path:
            # Use tmp_path to ensure we have a valid, resolvable base directory
            base = str(tmp_path)
            # resolve base to handle any symlinks in tmp path itself (e.g. /var vs /private/var)
            base = os.path.realpath(base)

            expected = os.path.join(base, "uploads", "image.png")
            self.assertEqual(safe_path_join(base, "uploads", "image.png"), expected)

            expected_css = os.path.join(base, "static", "css")
            self.assertEqual(safe_path_join(base, "static/css"), expected_css)

    def test_safe_path_join_traversal(self):
        """Test path traversal detection."""
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(str(tmp_path))

            with self.assertRaisesRegex(ValueError, "Path traversal detected"):
                safe_path_join(base, "../etc/passwd")

            with self.assertRaisesRegex(ValueError, "Path traversal detected"):
                # Note: we use os.path.join to construct the traversal string properly for the OS if needed,
                # but ".." is standard.
                safe_path_join(base, "uploads/../../etc/passwd")

    def test_safe_path_join_absolute_input(self):
        """Test handling of absolute inputs (should be treated as relative)."""
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(str(tmp_path))

            # Construct an absolute path. On Linux /etc/passwd, on Windows C:\etc\passwd
            abs_input = os.path.abspath(os.path.join(os.sep, "etc", "passwd"))

            # Our implementation treats absolute paths as relative by stripping the root
            # So /etc/passwd becomes etc/passwd inside base
            # We must replicate the stripping logic to assert correctly

            # Expected behavior:
            # 1. splitdrive (handles C:)
            # 2. lstrip sep
            # 3. join to base

            _, rel = os.path.splitdrive(abs_input)
            rel = rel.lstrip(os.path.sep)
            expected = os.path.join(base, rel)

            self.assertEqual(safe_path_join(base, abs_input), expected)

    def test_safe_path_join_null_bytes(self):
        """Test null byte injection."""
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(str(tmp_path))
            with self.assertRaisesRegex(ValueError, "Null byte found"):
                safe_path_join(base, "image.png\0.php")

    def test_safe_path_join_no_leakage(self):
        """Test that exception messages do not leak paths."""
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(str(tmp_path))
            try:
                safe_path_join(base, "../etc/passwd")
            except ValueError as e:
                msg = str(e)
                self.assertIn("Path traversal detected", msg)
                self.assertNotIn(base, msg)
                self.assertNotIn("/etc/passwd", msg)
            else:
                self.fail("ValueError not raised")

if __name__ == "__main__":
    unittest.main()