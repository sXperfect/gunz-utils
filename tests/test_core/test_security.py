import os
import tempfile
import unittest

from gunz_utils.security import open_path_under_base, safe_path_join, sanitize_filename


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

    def test_sanitize_filename_rejects_option_shaped_prefix(self):
        """Leading dashes are removed from sanitized basenames."""
        self.assertEqual(sanitize_filename("--danger.txt"), "danger.txt")
        self.assertEqual(sanitize_filename("-rf"), "rf")

    def test_sanitize_filename_bounds_replacement(self):
        with self.assertRaisesRegex(ValueError, "too long"):
            sanitize_filename(
                "file name.txt",
                replacement="x" * 17,
            )
        with self.assertRaisesRegex(ValueError, "control"):
            sanitize_filename(
                "file name.txt",
                replacement="x\n",
            )

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
                with self.assertRaisesRegex(
                    ValueError, "Replacement string contains unsafe path characters"
                ):
                    sanitize_filename("file*name.txt", replacement=replacement)

    def test_sanitize_filename_input_too_long(self):
        """Test that extremely long inputs are rejected to prevent DoS."""
        # 4096 is max, so 4097 should fail
        long_input = "a" * 4097
        with self.assertRaisesRegex(ValueError, "Input filename too long"):
            sanitize_filename(long_input)

        # 4096 should pass (and be truncated to 255)
        acceptable_input = "a" * 4096
        result = sanitize_filename(acceptable_input)
        self.assertEqual(len(result), 255)

    def test_safe_path_join_valid(self):
        """Test valid path joins."""
        with tempfile.TemporaryDirectory() as tmp_path:
            # Use tmp_path to ensure we have a valid, resolvable base directory
            base = str(tmp_path)
            # resolve base to handle any symlinks in tmp path itself
            # (e.g. /var vs /private/var)
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
                # Note: we use os.path.join to construct the traversal string
                # properly for the OS if needed, but ".." is standard.
                safe_path_join(base, "uploads/../../etc/passwd")

    def test_safe_path_join_absolute_input(self):
        """Absolute components are rejected rather than silently rewritten."""
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(str(tmp_path))
            abs_input = os.path.abspath(os.path.join(os.sep, "etc", "passwd"))
            with self.assertRaisesRegex(ValueError, "Absolute path components"):
                safe_path_join(base, abs_input)

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

    def test_absolute_component_is_rejected(self):
        with self.assertRaises(ValueError):
            safe_path_join("/tmp/base", "/etc/passwd")

    def test_open_path_under_base_reads_nested_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(tmp_path)
            nested = os.path.join(base, "nested")
            os.mkdir(nested)
            path = os.path.join(nested, "value.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("safe")
            with open_path_under_base(base, "nested", "value.txt", mode="r") as handle:
                self.assertEqual(handle.read(), "safe")

    @unittest.skipUnless(
        os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
        "requires POSIX O_NOFOLLOW",
    )
    def test_open_path_under_base_rejects_final_symlink(self):
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(tmp_path)
            outside = tempfile.NamedTemporaryFile(delete=False)
            outside.write(b"secret")
            outside.close()
            link = os.path.join(base, "link")
            try:
                os.symlink(outside.name, link)
                with self.assertRaises((OSError, ValueError)):
                    open_path_under_base(base, "link")
            finally:
                os.unlink(outside.name)

    @unittest.skipUnless(
        os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
        "requires POSIX O_NOFOLLOW",
    )
    def test_open_path_under_base_rejects_intermediate_symlink(self):
        with tempfile.TemporaryDirectory() as tmp_path:
            base = os.path.realpath(tmp_path)
            outside_dir = tempfile.mkdtemp()
            outside_file = os.path.join(outside_dir, "secret.txt")
            with open(outside_file, "w", encoding="utf-8") as handle:
                handle.write("secret")
            link = os.path.join(base, "nested")
            try:
                os.symlink(outside_dir, link)
                with self.assertRaises(ValueError):
                    open_path_under_base(base, "nested", "secret.txt")
            finally:
                import shutil

                shutil.rmtree(outside_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
