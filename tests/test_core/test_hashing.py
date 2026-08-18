"""Tests for hashing utilities."""

from __future__ import annotations

import hashlib
import pathlib
import tempfile
import unittest

from gunz_utils.hashing import (
    DEFAULT_ALGO,
    DEFAULT_CHUNK_SIZE,
    SUPPORTED_ALGOS,
    content_hash,
    file_hash,
    short_hash,
)


class TestContentHash(unittest.TestCase):
    def test_bytes_input(self) -> None:
        self.assertEqual(
            content_hash(b"hello"),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )

    def test_str_input_matches_bytes_utf8(self) -> None:
        self.assertEqual(content_hash("hello"), content_hash(b"hello"))

    def test_empty_bytes(self) -> None:
        self.assertEqual(content_hash(b""), hashlib.sha256(b"").hexdigest())

    def test_empty_string(self) -> None:
        self.assertEqual(content_hash(""), content_hash(b""))

    def test_sha256_default(self) -> None:
        self.assertEqual(content_hash(b"data"), hashlib.sha256(b"data").hexdigest())

    def test_sha512_algo(self) -> None:
        self.assertEqual(
            content_hash(b"data", algo="sha512"), hashlib.sha512(b"data").hexdigest()
        )

    def test_blake2b_algo(self) -> None:
        self.assertEqual(
            content_hash(b"data", algo="blake2b"), hashlib.blake2b(b"data").hexdigest()
        )

    def test_md5_algo(self) -> None:
        self.assertEqual(
            content_hash(b"data", algo="md5"), hashlib.md5(b"data").hexdigest()
        )

    def test_invalid_algo_raises_valueerror(self) -> None:
        with self.assertRaises(ValueError):
            content_hash(b"data", algo="unsupported")

    def test_int_input_raises_typeerror(self) -> None:
        _ = self.assertRaises(TypeError, content_hash, 42)

    def test_list_input_raises_typeerror(self) -> None:
        _ = self.assertRaises(TypeError, content_hash, [1, 2, 3])

    def test_none_input_raises_typeerror(self) -> None:
        _ = self.assertRaises(TypeError, content_hash, None)

    def test_unicode_string(self) -> None:
        self.assertEqual(content_hash("héllo"), content_hash("héllo".encode()))


class TestFileHash(unittest.TestCase):
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    directory: pathlib.Path = pathlib.Path()
    path: pathlib.Path = pathlib.Path()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = pathlib.Path(self.temp_dir.name)
        self.path = self.directory / "sample.bin"
        self.path.write_bytes(b"known file content")

    def tearDown(self) -> None:
        if self.temp_dir is not None:
            self.temp_dir.cleanup()

    def test_small_file(self) -> None:
        self.assertEqual(file_hash(self.path), content_hash(b"known file content"))

    def test_binary_file_with_null_bytes(self) -> None:
        data = b"\x00\x01\x02\x03"
        self.path.write_bytes(data)
        self.assertEqual(file_hash(self.path), content_hash(data))

    def test_empty_file(self) -> None:
        self.path.write_bytes(b"")
        self.assertEqual(file_hash(self.path), content_hash(b""))

    def test_default_algo_is_sha256(self) -> None:
        self.assertEqual(
            file_hash(self.path), hashlib.sha256(b"known file content").hexdigest()
        )

    def test_explicit_sha512(self) -> None:
        self.assertEqual(
            file_hash(self.path, algo="sha512"),
            hashlib.sha512(b"known file content").hexdigest(),
        )

    def test_pathlib_path_input(self) -> None:
        self.assertEqual(file_hash(self.path), content_hash(self.path.read_bytes()))

    def test_str_path_input(self) -> None:
        self.assertEqual(
            file_hash(str(self.path)), content_hash(self.path.read_bytes())
        )

    def test_file_not_found_propagates(self) -> None:
        with self.assertRaises(FileNotFoundError):
            file_hash(self.directory / "missing.bin")

    def test_directory_raises_isa_directory_error(self) -> None:
        with self.assertRaises(IsADirectoryError):
            file_hash(self.directory)

    def test_chunk_size_zero_raises(self) -> None:
        with self.assertRaises(ValueError):
            file_hash(self.path, chunk_size=0)

    def test_chunk_size_negative_raises(self) -> None:
        with self.assertRaises(ValueError):
            file_hash(self.path, chunk_size=-1)

    def test_invalid_algo_raises(self) -> None:
        with self.assertRaises(ValueError):
            file_hash(self.path, algo="unsupported")

    def test_large_file_streams(self) -> None:
        data = b"x" * 1_600_000
        self.path.write_bytes(data)
        expected_chunks = len(data) // DEFAULT_CHUNK_SIZE
        self.assertGreaterEqual(expected_chunks, 24)
        self.assertEqual(file_hash(self.path), content_hash(data))


class TestShortHash(unittest.TestCase):
    def test_default_chars_is_8(self) -> None:
        self.assertEqual(short_hash(b"hello"), content_hash(b"hello")[:8])
        self.assertEqual(len(short_hash(b"hello")), 8)

    def test_custom_chars(self) -> None:
        self.assertEqual(short_hash(b"hello", chars=12), content_hash(b"hello")[:12])

    def test_matches_content_hash_prefix(self) -> None:
        self.assertEqual(short_hash("data", chars=16), content_hash("data")[:16])

    def test_chars_below_minimum_raises(self) -> None:
        with self.assertRaises(ValueError):
            short_hash(b"data", chars=3)

    def test_chars_above_maximum_raises(self) -> None:
        with self.assertRaises(ValueError):
            short_hash(b"data", chars=129)

    def test_invalid_algo_raises(self) -> None:
        with self.assertRaises(ValueError):
            short_hash(b"data", algo="unsupported")

    def test_str_input(self) -> None:
        self.assertEqual(short_hash("héllo"), short_hash("héllo".encode()))


class TestConstantsExported(unittest.TestCase):
    def test_default_algo_value(self) -> None:
        self.assertEqual(DEFAULT_ALGO, "sha256")

    def test_default_chunk_size_value(self) -> None:
        self.assertEqual(DEFAULT_CHUNK_SIZE, 65536)

    def test_supported_algos_is_frozenset(self) -> None:
        self.assertIsInstance(SUPPORTED_ALGOS, frozenset)

    def test_supported_algos_contains_expected(self) -> None:
        self.assertTrue(
            {"sha256", "sha512", "sha1", "blake2b", "blake2s", "sha3_256", "md5"}
            <= SUPPORTED_ALGOS
        )


if __name__ == "__main__":
    unittest.main()
