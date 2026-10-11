"""Regression coverage for audit fixes: replay, invalidation, and validation."""

from __future__ import annotations

import asyncio
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from gunz_utils.binary import encode_uvarint
from gunz_utils.cache import async_ttl_cache
from gunz_utils.concurrency import process_imap, process_map
from gunz_utils.config import env_overrides
from gunz_utils.hashing import directory_manifest


def _identity(value: int) -> int:
    return value


class _PartialFailureExecutor:
    def __init__(self, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "_PartialFailureExecutor":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def map(self, func: object, items: object, **kwargs: object):
        yield 1
        raise RuntimeError("worker failed after partial work")


class TestProcessReplay(unittest.TestCase):
    def test_map_does_not_replay_partial_failure(self) -> None:
        with patch(
            "gunz_utils.concurrency.concurrent.futures.ProcessPoolExecutor",
            _PartialFailureExecutor,
        ):
            with self.assertRaisesRegex(RuntimeError, "partial work"):
                process_map(_identity, [1, 2], workers=2, threshold=0)

    def test_imap_does_not_duplicate_yielded_values(self) -> None:
        with patch(
            "gunz_utils.concurrency.concurrent.futures.ProcessPoolExecutor",
            _PartialFailureExecutor,
        ):
            iterator = process_imap(_identity, [1, 2], workers=2, threshold=0)
            self.assertEqual(next(iterator), 1)
            with self.assertRaisesRegex(RuntimeError, "partial work"):
                next(iterator)

    def test_empty_input_still_checks_workers(self) -> None:
        with self.assertRaises(ValueError):
            process_map(_identity, [], workers=0)
        with self.assertRaises(ValueError):
            list(process_imap(_identity, [], workers=0))


class TestAsyncInvalidation(unittest.IsolatedAsyncioTestCase):
    async def test_clear_during_production_cannot_reinsert_stale_value(self) -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        @async_ttl_cache(ttl=60)
        async def fetch(key: int) -> int:
            nonlocal calls
            calls += 1
            version = calls
            if version == 1:
                started.set()
                await release.wait()
            return version

        old = asyncio.create_task(fetch(1))
        await started.wait()
        await fetch.cache_clear()
        self.assertEqual(await fetch(1), 2)
        release.set()
        self.assertEqual(await old, 1)
        self.assertEqual(await fetch(1), 2)
        self.assertEqual(calls, 2)


class TestValidation(unittest.TestCase):
    def test_env_scalar_nested_conflicts_in_both_orders(self) -> None:
        first = [("APP_DB", "sqlite"), ("APP_DB__HOST", "localhost")]
        for sequence in (first, list(reversed(first))):
            with self.subTest(sequence=sequence):
                with self.assertRaises(ValueError):
                    env_overrides(dict(sequence), prefix="APP")

    def test_varint_rejects_boolean(self) -> None:
        for value in (True, False):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    encode_uvarint(value)


class TestDirectoryManifest(unittest.TestCase):
    def test_rejected_secure_open_fails_instead_of_omitting_file(self) -> None:
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            (root / "important.txt").write_text("data", encoding="utf-8")
            with patch(
                "gunz_utils.security.open_path_under_base",
                side_effect=ValueError("unsafe path"),
            ):
                with self.assertRaisesRegex(ValueError, "unsafe path"):
                    directory_manifest(root)

    def test_directory_manifest_still_excludes_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported")
            self.assertNotIn("link.txt", directory_manifest(root))


class _StreamingExecutor:
    def __init__(self, **kwargs: object) -> None:
        pass

    def __enter__(self) -> "_StreamingExecutor":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def map(self, func, items, **kwargs):
        for item in items:
            yield func(item)


class TestStreamingProcessMap(unittest.TestCase):
    def test_generator_consumption_is_bounded_before_first_result(self) -> None:
        consumed = []

        def source():
            for value in range(1000):
                consumed.append(value)
                yield value

        with patch(
            "gunz_utils.concurrency.concurrent.futures.ProcessPoolExecutor",
            _StreamingExecutor,
        ):
            results = process_imap(_identity, source(), workers=2, threshold=0)
            self.assertEqual(next(results), 0)
            self.assertLessEqual(len(consumed), 5)
            self.assertEqual(list(results), list(range(1, 1000)))

    def test_empty_generator_rejects_invalid_chunksize(self) -> None:
        with self.assertRaises(ValueError):
            list(process_imap(_identity, iter(()), chunksize=0))


class TestEventLoopReuse(unittest.TestCase):
    def test_async_cache_reusable_across_completed_event_loops(self) -> None:
        calls = []

        @async_ttl_cache(ttl=60)
        async def compute(value: int) -> int:
            calls.append(value)
            return value * 2

        self.assertEqual(asyncio.run(compute(1)), 2)
        self.assertEqual(asyncio.run(compute(1)), 2)
        self.assertEqual(asyncio.run(compute(2)), 4)
        self.assertEqual(calls, [1, 2])
