from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from gunz_utils.fs import (
    atomic_write_bytes,
    contained_path,
    lexical_contained_path,
    transactional_directory,
)
from gunz_utils.streaming import fingerprint, hash_stream, iter_jsonl, write_jsonl
from gunz_utils.structures import RingBuffer, stable_unique, top_k


class TestM8M10(unittest.TestCase):
    def test_structures(self) -> None:
        ring = RingBuffer[int](2)
        for value in [1, 2, 3]:
            ring.append(value)
        self.assertEqual(list(ring), [2, 3])
        self.assertEqual(list(stable_unique([2, 1, 2, 3, 1])), [2, 1, 3])
        self.assertEqual(top_k(range(10), 3), [9, 8, 7])

    def test_structure_bounds_reject_boolean_sizes(self) -> None:
        with self.assertRaises(ValueError):
            RingBuffer[int](True)
        with self.assertRaises(ValueError):
            top_k([1, 2, 3], True)

    def test_filesystem_safety(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "value.bin"
            atomic_write_bytes(target, b"abc")
            self.assertEqual(target.read_bytes(), b"abc")
            self.assertEqual(contained_path(root, "a/b"), root.resolve() / "a/b")
            self.assertEqual(lexical_contained_path(root, "a/b"), root / "a/b")
            with self.assertRaises(ValueError):
                contained_path(root, "../escape")
            with self.assertRaises(ValueError):
                lexical_contained_path(root, "../escape")
            with self.assertRaises(ValueError):
                lexical_contained_path(root, root / "absolute")
            final = root / "published"
            with transactional_directory(final) as staging:
                (staging / "x").write_text("ok")
            self.assertEqual((final / "x").read_text(), "ok")

    def test_streaming(self) -> None:
        output = io.StringIO()
        self.assertEqual(write_jsonl(output, [{"b": 2}, {"a": 1}]), 2)
        output.seek(0)
        self.assertEqual(list(iter_jsonl(output)), [{"b": 2}, {"a": 1}])
        self.assertEqual(fingerprint({"a": 1, "b": 2}), fingerprint({"b": 2, "a": 1}))
        self.assertEqual(len(hash_stream(io.BytesIO(b"abc"))), 64)


if __name__ == "__main__":
    unittest.main()
