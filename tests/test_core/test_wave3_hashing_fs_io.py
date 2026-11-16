"""Tests for Wave 3 additions: Cryptographic Hashing, Filesystem & Atomic I/O (#28 -
#42).
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from gunz_utils.fs import (
    ensure_dir,
    matches_any_glob,
    tree_fingerprint,
    walk_files,
)
from gunz_utils.hashing import (
    content_hash,
    file_hash,
    hmac_digest,
    short_hash,
    structured_hash,
    verify_hmac,
)
from gunz_utils.io import (
    atomic_json_read,
    atomic_json_write,
    atomic_write,
    physical_lines,
    safe_read_bytes,
    safe_read_text,
)


class TestWave3Hashing(unittest.TestCase):
    def test_item28_content_hash_and_short_hash_buffer_types(self) -> None:
        data = b"benchmark payload"
        ba = bytearray(data)
        mv = memoryview(data)

        expected = content_hash(data)
        self.assertEqual(content_hash(ba), expected)
        self.assertEqual(content_hash(mv), expected)

        short_exp = short_hash(data, chars=12)
        self.assertEqual(short_hash(ba, chars=12), short_exp)
        self.assertEqual(short_hash(mv, chars=12), short_exp)

    def test_item29_file_hash_fifo_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fifo_path = tmp_path / "test.fifo"
            if hasattr(os, "mkfifo"):
                os.mkfifo(fifo_path)
                with self.assertRaises(ValueError):
                    file_hash(fifo_path)

    def test_item30_hmac_digest_and_verify(self) -> None:
        key = b"secret-key"
        msg = b"authenticated-message"

        digest = hmac_digest(key, msg, algo="sha256")
        self.assertIsInstance(digest, str)
        self.assertEqual(len(digest), 64)

        #? verify_hmac
        self.assertTrue(verify_hmac(key, msg, digest, algo="sha256"))
        self.assertFalse(verify_hmac(key, b"tampered", digest, algo="sha256"))
        self.assertFalse(verify_hmac(b"wrong-key", msg, digest, algo="sha256"))

        #? String key/message support
        digest_str = hmac_digest("secret-key", "authenticated-message")
        self.assertEqual(digest_str, digest)

        with self.assertRaises(TypeError):
            verify_hmac(key, msg, 12345)  # type: ignore[arg-type]

    def test_item31_structured_hash_bytearray_memoryview(self) -> None:
        b = b"bytes123"
        ba = bytearray(b)
        mv = memoryview(b)

        h_bytes = structured_hash({"payload": b})
        h_ba = structured_hash({"payload": ba})
        h_mv = structured_hash({"payload": mv})

        self.assertEqual(h_bytes, h_ba)
        self.assertEqual(h_bytes, h_mv)


class TestWave3Filesystem(unittest.TestCase):
    def test_item32_matches_any_glob_bare_string_rejection(self) -> None:
        with self.assertRaises(TypeError):
            matches_any_glob("foo.py", "*.py")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            matches_any_glob("foo.py", b"*.py")  # type: ignore[arg-type]

        self.assertTrue(matches_any_glob("foo.py", ["*.py"]))
        self.assertFalse(matches_any_glob("foo.txt", ["*.py"]))

    def test_item33_and_34_walk_files_and_tree_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "a.py").write_text("print(1)")
            (root / "b.txt").write_text("hello")
            sub = root / "sub"
            sub.mkdir()
            (sub / "c.py").write_text("print(2)")

            #? Bare strings must be rejected
            with self.assertRaises(TypeError):
                list(walk_files(root, include="*.py"))  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                list(walk_files(root, exclude="*.txt"))  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                list(walk_files(root, extensions=".py"))  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                tree_fingerprint(root, exclude="sub")  # type: ignore[arg-type]

            #? Valid walks
            files = list(walk_files(root, extensions=[".py"]))
            self.assertEqual(len(files), 2)
            fp = tree_fingerprint(root, extensions=[".py"])
            self.assertIsInstance(fp, str)
            self.assertEqual(len(fp), 64)

    def test_item35_ensure_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "a" / "b" / "c"
            res = ensure_dir(target)
            self.assertTrue(res.is_dir())
            self.assertEqual(res, target)

            #? Idempotent
            res2 = ensure_dir(target)
            self.assertEqual(res2, target)

            #? Rejects existing file
            file_path = root / "a_file.txt"
            file_path.write_text("hello")
            with self.assertRaises(NotADirectoryError):
                ensure_dir(file_path)

            #? Rejects symlink
            sym = root / "sym_dir"
            sym.symlink_to(target)
            with self.assertRaises(ValueError):
                ensure_dir(sym)


class TestWave3IO(unittest.TestCase):
    def test_item36_and_37_atomic_write_pre_tempfile_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "out.txt"

            #? Pre-tempfile validation: invalid types do not create temp files
            with self.assertRaises(TypeError):
                atomic_write(target, 12345)  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                atomic_write(target, "ok", mkdir="no")  # type: ignore[arg-type]
            with self.assertRaises(TypeError):
                atomic_write(target, "ok", durable="yes")  # type: ignore[arg-type]

            self.assertFalse(target.exists())
            self.assertEqual(list(root.iterdir()), [])

            #? Target is directory
            dir_path = root / "existing_dir"
            dir_path.mkdir()
            with self.assertRaises(IsADirectoryError):
                atomic_write(dir_path, "content")

            #? Supports bytearray and memoryview in binary mode
            bin_target = root / "bin.dat"
            atomic_write(bin_target, bytearray(b"binary data"), mode="wb")
            self.assertEqual(bin_target.read_bytes(), b"binary data")

            atomic_write(bin_target, memoryview(b"new binary"), mode="wb")
            self.assertEqual(bin_target.read_bytes(), b"new binary")

    def test_item38_atomic_json_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            json_file = root / "data.json"
            atomic_json_write(json_file, {"key": "value", "items": [1, 2, 3]})

            data = atomic_json_read(json_file)
            self.assertEqual(data, {"key": "value", "items": [1, 2, 3]})

            #? max_bytes enforcement
            with self.assertRaises(ValueError):
                atomic_json_read(json_file, max_bytes=5)

            #? Non-regular file rejection
            with self.assertRaises(IsADirectoryError):
                atomic_json_read(root)

    def test_item39_physical_lines_keepends_validation(self) -> None:
        with self.assertRaises(TypeError):
            physical_lines("hello\nworld", keepends=1)  # type: ignore[arg-type]
        self.assertEqual(
    physical_lines(
        "hello\nworld", keepends=False), [
            "hello", "world"])
        self.assertEqual(
    physical_lines(
        "hello\nworld", keepends=True), [
            "hello\n", "world"])

    def test_item40_safe_read_bytes_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            f = root / "file.txt"
            f.write_text("safe content")

            sym = root / "sym.txt"
            sym.symlink_to(f)

            #? Read via symlink allowed when True
            self.assertEqual(safe_read_text(sym, allow_symlink=True), "safe content")
            self.assertEqual(safe_read_bytes(sym, allow_symlink=True), b"safe content")

            #? Symlink rejected when False
            with self.assertRaises(ValueError):
                safe_read_text(sym, allow_symlink=False)
            with self.assertRaises(ValueError):
                safe_read_bytes(sym, allow_symlink=False)

            #? max_bytes check
            with self.assertRaises(ValueError):
                safe_read_bytes(f, max_bytes=4)


if __name__ == "__main__":
    unittest.main()
