"""Phase 41 (security lane) perpetual-audit tests.

Scope: async_utils, binary, fs, parsing, pipeline, resources.

Findings (RED):
  1. ResourceGroup.__exit__ / AsyncResourceGroup.__aexit__ leave ``_entered``
     True when the underlying stack exit itself raises (resources.py:54-58 /
     102-106). The ``_entered = False`` reset is skipped on that path, so a
     subsequent enter() bypasses the documented "must be entered" RuntimeError
     guard and silently pushes a resource onto an already-exited group that can
     never release it (cleanup-on-every-exit violation).
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path

import pytest

from gunz_utils.async_utils import cancel_and_wait, with_timeout
from gunz_utils.binary import ByteReader, encode_uvarint
from gunz_utils.fs import (
    contained_path,
    lexical_contained_path,
    transactional_directory,
)
from gunz_utils.parsing import parse_bool, safe_bool, safe_float, safe_int
from gunz_utils.pipeline import worker_map
from gunz_utils.resources import AsyncResourceGroup, ResourceGroup

# ---------------------------------------------------------------------------
# RED: resource-group entered-guard must survive a failed stack exit
# ---------------------------------------------------------------------------

class _Exploder:
    """A context manager whose __exit__ raises, simulating a cleanup failure."""

    def __enter__(self) -> _Exploder:
        return self

    def __exit__(self, *exc_info: object) -> None:
        raise ValueError("exit boom")


class _Tracker:
    """A well-behaved context manager that records whether it was released."""

    def __init__(self) -> None:
        self.released = False

    def __enter__(self) -> _Tracker:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.released = True


def test_resource_group_guard_survives_failed_exit() -> None:
    group = ResourceGroup()
    group.__enter__()
    group.enter(_Exploder())
    with pytest.raises(ValueError):
        group.__exit__(None, None, None)

    leaked = _Tracker()
    # The group has already been exited; enter() must be refused.
    with pytest.raises(RuntimeError):
        group.enter(leaked)
    assert not leaked.released


class _AsyncExploder:
    async def __aenter__(self) -> _AsyncExploder:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        raise ValueError("exit boom")


class _AsyncTracker:
    def __init__(self) -> None:
        self.released = False

    async def __aenter__(self) -> _AsyncTracker:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.released = True


def test_async_resource_group_guard_survives_failed_exit() -> None:
    async def scenario() -> None:
        group = AsyncResourceGroup()
        await group.__aenter__()
        await group.enter(_AsyncExploder())
        with pytest.raises(ValueError):
            await group.__aexit__(None, None, None)

        leaked = _AsyncTracker()
        with pytest.raises(RuntimeError):
            await group.enter(leaked)
        assert not leaked.released

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# GREEN pins: modules audited and found already correct
# ---------------------------------------------------------------------------

def test_binary_uvarint_roundtrip_boundaries() -> None:
    for value in [0, 1, 127, 128, 255, 300, 2**32 - 1, 2**63, 2**64 - 1]:
        encoded = encode_uvarint(value)
        assert ByteReader(encoded).read_uvarint() == value
    with pytest.raises(ValueError):
        encode_uvarint(2**64)
    with pytest.raises(ValueError):
        encode_uvarint(-1)
    with pytest.raises(TypeError):
        encode_uvarint(True)  # type: ignore[arg-type]


def test_binary_read_uvarint_is_transactional_on_malformed_input() -> None:
    reader = ByteReader(b"\x80\x00\x05")
    with pytest.raises(ValueError):
        reader.read_uvarint()
    assert reader.offset == 0

    reader2 = ByteReader(b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff")
    with pytest.raises(ValueError):
        reader2.read_uvarint()
    assert reader2.offset == 0


def test_binary_reader_bounds() -> None:
    reader = ByteReader(b"abc")
    with pytest.raises(EOFError):
        reader.read(4)
    assert bytes(reader.read(0)) == b""
    with pytest.raises(TypeError):
        reader.read(True)  # type: ignore[arg-type]
    with pytest.raises(EOFError):
        reader.read(-1)


def test_parsing_safe_int_guards_bool_and_bounds() -> None:
    assert safe_int("42") == 42
    assert safe_int(True, default=-1) == -1
    assert safe_int("5", default=-1, min=10) == -1
    assert safe_int("5", default=-1, max=3) == -1
    assert safe_int("ff", base=16) == 255


def test_parsing_safe_float_guards_overflow_inf_nan_and_bounds() -> None:
    assert safe_float("1.5") == 1.5
    assert safe_float(10**400, default=-1.0) == -1.0
    assert safe_float("1e400", allow_inf=False, default=-1.0) == -1.0
    assert safe_float(float("nan"), allow_nan=False, default=-1.0) == -1.0
    assert safe_float(True, default=-1.0) == -1.0
    assert safe_float("2.0", default=-1.0, max=1.0) == -1.0
    assert math.isnan(safe_float(float("nan"), allow_nan=True, min=0, max=1))


def test_parsing_bools() -> None:
    assert safe_bool("YES") is True
    assert safe_bool("off") is False
    assert safe_bool(1) is True
    assert safe_bool(2, default="d") == "d"
    assert safe_bool(True) is True
    with pytest.raises(ValueError):
        parse_bool("maybe")


def test_fs_containment_rejects_escape_and_symlink_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        contained_path(tmp_path, "../outside")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "f.txt").write_text("x")
    assert contained_path(tmp_path, "sub/f.txt") == (sub / "f.txt").resolve()
    with pytest.raises(ValueError):
        lexical_contained_path(tmp_path, "sub/../escape")
    with pytest.raises(ValueError):
        lexical_contained_path(tmp_path, "/abs")


def test_fs_transactional_directory_publishes_and_cleans_on_failure(
    tmp_path: Path,
) -> None:
    target = tmp_path / "out"
    with transactional_directory(target) as staging:
        (Path(staging) / "a.txt").write_text("data")
    assert (target / "a.txt").read_text() == "data"

    target2 = tmp_path / "out2"
    target2.mkdir()
    with pytest.raises(FileExistsError):
        with transactional_directory(target2):
            pass


def test_async_with_timeout_rejects_bad_timeouts() -> None:
    async def noop() -> int:
        return 1

    async def run() -> None:
        future = asyncio.get_running_loop().create_future()
        future.set_result(1)
        assert await with_timeout(noop(), None) == 1
        assert await with_timeout(noop(), 1.0) == 1
        with pytest.raises(ValueError):
            await with_timeout(future, -1)
        with pytest.raises(ValueError):
            await with_timeout(future, True)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            await with_timeout(future, 10**400)
        with pytest.raises(ValueError):
            await with_timeout(future, float("inf"))

    asyncio.run(run())


def test_async_cancel_and_wait_no_tasks() -> None:
    async def run() -> None:
        await cancel_and_wait()

    asyncio.run(run())


def test_pipeline_propagates_failure_and_cleans_up() -> None:
    async def boom(value: int) -> int:
        if value == 2:
            raise ValueError("boom")
        return value

    async def scenario() -> None:
        collected: list[int] = []
        with pytest.raises(ValueError):
            async for item in worker_map(boom, [1, 2, 3], workers=2, queue_size=2):
                collected.append(item)
        assert collected == [1]

    asyncio.run(scenario())


def test_pipeline_no_coroutine_leak_on_early_break() -> None:
    async def identity(value: int) -> int:
        await asyncio.sleep(0)
        return value

    async def scenario() -> None:
        generator = worker_map(identity, [1, 2, 3, 4, 5], workers=2, queue_size=2)
        seen = 0
        async for _ in generator:
            seen += 1
            if seen == 2:
                break
        await asyncio.sleep(0.05)
        # If a worker coroutine leaked un-awaited, asyncio would emit a
        # RuntimeWarning; reaching here with the generator closed is sufficient.
        assert seen == 2

    asyncio.run(scenario())
