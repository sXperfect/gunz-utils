from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from gunz_utils.benchmark import PerformanceRun, SystemInfo, register_artifact, save_run_directory
from gunz_utils.binary import ByteReader, encode_uvarint
from gunz_utils.fs import lexical_contained_path
from gunz_utils.pipeline import worker_map


class TestAuditRegressions(unittest.IsolatedAsyncioTestCase):
    async def test_worker_map_completes_without_deadlock(self) -> None:
        async def work(value: int) -> int:
            return value

        result = [
            value
            async for value in worker_map(work, range(5), workers=2, queue_size=1)
        ]
        self.assertEqual(sorted(result), list(range(5)))

    async def test_worker_map_propagates_error(self) -> None:
        async def work(value: int) -> int:
            if value == 2:
                raise OSError("boom")
            return value

        with self.assertRaises(OSError):
            _ = [value async for value in worker_map(work, range(5), workers=2)]

    async def test_varint_failure_is_transactional(self) -> None:
        reader = ByteReader(b"\x80")
        with self.assertRaises(EOFError):
            reader.read_uvarint()
        self.assertEqual(reader.offset, 0)

    async def test_varint_rejects_overflow(self) -> None:
        with self.assertRaises(ValueError):
            encode_uvarint(2**64)

    async def test_lexical_containment(self) -> None:
        root = Path("/tmp/root")
        self.assertEqual(lexical_contained_path(root, "a/b"), root / "a/b")
        with self.assertRaises(ValueError):
            lexical_contained_path(root, "../escape")
        with self.assertRaises(ValueError):
            lexical_contained_path(root, "/absolute")

    async def test_duplicate_artifact_basenames_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_dir, second_dir = root / "a", root / "b"
            first_dir.mkdir()
            second_dir.mkdir()
            first, second = first_dir / "same.bin", second_dir / "same.bin"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            run = PerformanceRun("demo", SystemInfo.capture())
            run = register_artifact(run, first, kind="x")
            run = register_artifact(run, second, kind="x")
            packaged = save_run_directory(run, root / "run")
            paths = [Path(item.path) for item in packaged.artifacts]
            self.assertEqual(len({path.name for path in paths}), 2)
            self.assertEqual({path.read_bytes() for path in paths}, {b"one", b"two"})


if __name__ == "__main__":
    unittest.main()
