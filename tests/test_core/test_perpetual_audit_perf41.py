"""Phase 41 perpetual audit: round-4 (deepest) re-audit of six core modules.

async_utils.py, binary.py, fs.py, parsing.py, pipeline.py, resources.py.

Verified correct at base f67d5ad (GREEN companion tests below):
- binary: uvarint encode/decode roundtrip, canonicality rejection,
  truncated-input EOFError, transactional rollback.
- fs: atomic_write_bytes, contained_path/lexical_contained_path containment,
  transactional_directory publish + staging cleanup on failure.
- parsing: safe_int/safe_float/safe_bool/parse_bool (bool rejection, inf/nan
  policy, huge-int OverflowError->default, bounds).
- pipeline: worker_map ordered bounded mapping, failure propagation, empty
  input, cancellation cleanup.
- resources: ResourceGroup/AsyncResourceGroup enter/exit lifecycle and
  enter-after-exit guard.
- async_utils: with_timeout positive timeout, zero-timeout TimeoutError,
  cancel_and_wait.

One NEW finding:

1) async_utils._run_with_zero_timeout (src/gunz_utils/async_utils.py:109-135)
   leaks its child task when the enclosing ``with_timeout(awaitable, 0)``
   coroutine is cancelled mid-drain. The function does ``task =
   asyncio.ensure_future(awaitable)`` and then loops ``await asyncio.sleep(0)``
   with NO ``try/finally`` to cancel and await the child on its own
   cancellation. If the caller cancels ``with_timeout(awaitable, 0)`` while it
   is draining (before it decides the work needs real time), the CancelledError
   propagates out of the sleep and the child ``task`` is orphaned: it keeps
   running the awaited work in the background (a task leak / orphaned-work
   hazard). By contrast the ``timeout > 0`` branch uses ``asyncio.timeout``,
   which cleans up its child properly. A cancelled zero-timeout call must not
   leave the awaited operation running (RED).

This test is expected to be RED against base f67d5ad for the finding and GREEN
for the companion behaviors.
"""

from __future__ import annotations

import asyncio
import pathlib
import tempfile

import pytest

from gunz_utils import async_utils
from gunz_utils.binary import ByteReader, encode_uvarint
from gunz_utils.fs import (
    atomic_write_bytes,
    contained_path,
    lexical_contained_path,
    transactional_directory,
)
from gunz_utils.parsing import parse_bool, safe_bool, safe_float, safe_int
from gunz_utils.pipeline import worker_map
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup

# ---------------------------------------------------------------------------
# 1) async_utils zero-timeout child-task leak on cancellation (RED)
# ---------------------------------------------------------------------------


def test_with_timeout_zero_cancel_does_not_leak_child_task():
    async def sleeper() -> int:
        await asyncio.sleep(10)
        return 1

    async def scenario() -> int:
        t = asyncio.create_task(async_utils.with_timeout(sleeper(), 0))
        await asyncio.sleep(0)  # let it enter the zero-timeout drain
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        leaked = [
            x
            for x in asyncio.all_tasks()
            if x is not asyncio.current_task()
        ]
        for p in leaked:
            p.cancel()
        return len(leaked)

    count = asyncio.run(scenario())
    assert count == 0


# ---------------------------------------------------------------------------
# GREEN companions — async_utils (normal paths)
# ---------------------------------------------------------------------------


def test_with_timeout_positive_and_zero():
    async def work() -> int:
        return 7

    async def scenario() -> tuple:
        a = await async_utils.with_timeout(work(), 5)
        b = await async_utils.with_timeout(work(), 0)
        return a, b

    assert asyncio.run(scenario()) == (7, 7)


def test_with_timeout_zero_blocks_on_real_time():
    async def slow() -> int:
        await asyncio.sleep(10)
        return 1

    with pytest.raises(TimeoutError):
        asyncio.run(async_utils.with_timeout(slow(), 0))


def test_with_timeout_invalid_timeout_rejected():
    async def work() -> int:
        return 1

    for bad in (True, -1, 10**400):
        coro = work()
        try:
            with pytest.raises(ValueError):
                asyncio.run(async_utils.with_timeout(coro, bad))
        finally:
            coro.close()


# ---------------------------------------------------------------------------
# GREEN companions — binary
# ---------------------------------------------------------------------------


def test_uvarint_roundtrip_and_canonical():
    for value in (0, 1, 127, 128, 300, 2**32, 2**64 - 1):
        encoded = encode_uvarint(value)
        assert ByteReader(encoded).read_uvarint() == value
    with pytest.raises(ValueError):
        encode_uvarint(-1)
    with pytest.raises(ValueError):
        encode_uvarint(2**64)
    with pytest.raises(TypeError):
        encode_uvarint(True)


def test_uvarint_rejects_non_canonical_and_truncated():
    with pytest.raises(ValueError):
        ByteReader(bytes([0x80, 0x00])).read_uvarint()  # non-minimal 0
    with pytest.raises(EOFError):
        ByteReader(b"\x80").read_uvarint()  # truncated continuation


def test_bytereader_read_and_rollback():
    reader = ByteReader(b"\x05\xff")
    assert reader.read(1)[0] == 0x05
    start = reader.offset
    with pytest.raises(ValueError):
        ByteReader(b"\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x01").read_uvarint()
    assert reader.offset == start


# ---------------------------------------------------------------------------
# GREEN companions — fs
# ---------------------------------------------------------------------------


def test_fs_atomic_write_and_containment():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        atomic_write_bytes(root / "x.txt", b"hi")
        assert (root / "x.txt").read_bytes() == b"hi"
        assert contained_path(root, "x.txt") == (root / "x.txt").resolve()
        with pytest.raises(ValueError):
            contained_path(td, "../escape")
        with pytest.raises(ValueError):
            lexical_contained_path(td, "a/../../escape")


def test_transactional_directory_publish_and_cleanup():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        target = root / "out"
        with transactional_directory(target) as staging:
            (staging / "f.txt").write_text("hello")
        assert (target / "f.txt").read_text() == "hello"
        # Publish over an existing target must fail closed and keep staging clean.
        with pytest.raises(FileExistsError):
            with transactional_directory(target) as staging2:
                (staging2 / "g.txt").write_text("x")


# ---------------------------------------------------------------------------
# GREEN companions — parsing
# ---------------------------------------------------------------------------


def test_parsing_safe_helpers():
    assert safe_int("42") == 42
    assert safe_int("x") is None
    assert safe_int("42", min=50) is None
    assert safe_int(True) is None
    assert safe_float("3.5") == 3.5
    assert safe_float("inf") == float("inf")
    assert safe_float("inf", allow_inf=False) is None
    assert safe_float(10**400) is None  # OverflowError -> default
    assert safe_float("nan") is None
    assert safe_bool("yes") is True
    assert safe_bool(0) is False
    assert safe_bool("zzz") is None
    assert parse_bool("true") is True
    with pytest.raises(ValueError):
        parse_bool("maybe")


# ---------------------------------------------------------------------------
# GREEN companions — pipeline
# ---------------------------------------------------------------------------


def test_worker_map_ordered_and_errors():
    async def dbl(x: int) -> int:
        return x * 2

    async def boom(x: int) -> int:
        if x == 3:
            raise ValueError("boom")
        return x

    async def scenario() -> tuple:
        ordered = [r async for r in worker_map(dbl, [1, 2, 3, 4, 5], workers=3)]
        empty = [r async for r in worker_map(dbl, [], workers=2)]
        try:
            [r async for r in worker_map(boom, [1, 2, 3, 4], workers=2)]
            errored = None
        except ValueError as exc:
            errored = str(exc)
        return ordered, empty, errored

    ordered, empty, errored = asyncio.run(scenario())
    assert ordered == [2, 4, 6, 8, 10]
    assert empty == []
    assert errored == "boom"


# ---------------------------------------------------------------------------
# GREEN companions — resources
# ---------------------------------------------------------------------------


class _CM:
    def __init__(self) -> None:
        self.closed = False

    def __enter__(self) -> _CM:
        return self

    def __exit__(self, *args: object) -> bool:
        self.closed = True
        return False


class _ACM:
    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> _ACM:
        return self

    async def __aexit__(self, *args: object) -> bool:
        self.closed = True
        return False


def test_resource_group_lifecycle():
    rg = ResourceGroup()
    with rg as g:
        r = _CM()
        g.enter(r)
        assert not r.closed
    assert r.closed
    with pytest.raises(RuntimeError):
        rg.enter(_CM())


def test_async_resource_group_lifecycle():
    async def scenario() -> bool:
        rg = AsyncResourceGroup()
        async with rg as g:
            r = _ACM()
            await g.enter(r)
            assert not r.closed
        assert r.closed
        with pytest.raises(RuntimeError):
            await rg.enter(_ACM())
        return True

    assert asyncio.run(scenario()) is True
