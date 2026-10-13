"""Perpetual security audit phase 26 (round 4, deepest).

Re-audit of ``concurrency``, ``io``, ``dag``, and ``leases``.

Findings:

1. ``atomic_write`` accepts ``mode`` values it does not honor, silently
   discarding data.

   In io.py:76-80 the only mode classification is ``is_binary = "b" in mode``,
   and the temp file is written via ``os.fdopen(fd, mode, ...)`` (io.py:103).
   The temp file is created by ``tempfile.mkstemp`` and then atomically
   replaced, so the ONLY modes that are meaningful for an atomic-replace write
   are ``"w"`` / ``"wb"``.  An append mode ``"a"`` is accepted and silently
   behaves like ``"w"`` (each call writes a fresh temp and replaces the
   target), so a caller using ``mode="a"`` loses previously stored content.
   ``mode="x"`` always fails with a confusing ``ValueError: file exists``
   (the mkstemp temp already exists), and ``mode="r"`` fails on write.  These
   modes should be rejected up front with a clear ``ValueError`` instead of
   silently replacing (data loss) or failing in a misleading way.

2. ``WorkflowDAG.execute`` (sync) drives async ``run`` stages with
   ``asyncio.run``, which cannot run from a running event loop.

   dag.py:496-500 calls ``asyncio.run(output)`` when a stage's ``run`` returns
   a coroutine.  ``WorkflowStage.run`` is documented to "be synchronous or an
   async coroutine function" and ``execute`` is the documented synchronous
   entry point.  When ``execute`` is called from inside a running event loop
   (a common pattern, e.g. a sync helper invoked from async code), the
   ``asyncio.run`` call raises ``RuntimeError: asyncio.run() cannot be called
   from a running event loop``, which is then caught by ``except BaseException``
   (dag.py:501) and misreported as ``WorkflowExecutionError`` claiming the
   *stage* failed.  The never-driven stage coroutine is also leaked (it is
   never awaited or closed), producing a "coroutine was never awaited" warning.

   Expected: sync ``execute`` must not leak the stage coroutine and must not
   misreport the event-loop conflict as a stage failure -- it should either
   drive the coroutine to completion or raise a clear, correct error while
   closing the coroutine.
"""

import asyncio
import gc
import warnings

import pytest

from gunz_utils.dag import WorkflowDAG, WorkflowExecutionError, WorkflowStage
from gunz_utils.io import atomic_write


async def _async_stage(deps: dict) -> str:
    await asyncio.sleep(0)
    return "done"


def test_atomic_write_rejects_unsupported_append_mode(tmp_path):
    """RED: ``mode="a"`` is accepted but silently replaces (discards) existing
    content instead of appending.  Unsupported modes must be rejected.
    """
    path = tmp_path / "log.txt"
    atomic_write(path, "first")
    with pytest.raises(ValueError):
        atomic_write(path, "second", mode="a")


def test_atomic_write_rejects_exclusive_mode(tmp_path):
    """RED: ``mode="x"`` fails with a misleading ``ValueError: file exists``
    (the mkstemp temp file already exists) rather than being rejected as an
    unsupported mode up front.
    """
    path = tmp_path / "exclusive.txt"
    with pytest.raises(ValueError) as excinfo:
        atomic_write(path, "content", mode="x")
    assert "exists" not in str(excinfo.value)


def test_sync_execute_async_stage_in_running_loop_does_not_leak():
    """RED: sync ``execute`` driven from a running event loop with an async
    ``run`` stage misreports the ``asyncio.run`` conflict as a stage failure
    and leaks the stage coroutine.
    """
    dag = WorkflowDAG([WorkflowStage("a", run=_async_stage)])

    async def main() -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                dag.execute()
            except WorkflowExecutionError:
                raise AssertionError(
                    "sync execute() misreported an async stage driven from a "
                    "running loop as a stage failure"
                ) from None
            gc.collect()
        leaks = [
            str(w.message)
            for w in caught
            if "never awaited" in str(w.message).lower()
        ]
        assert not leaks, f"leaked un-awaited coroutines: {leaks}"

    asyncio.run(main())


def test_sync_execute_async_stage_without_running_loop(tmp_path):
    """Green sanity: outside a running loop, sync execute drives an async
    stage via asyncio.run and returns its output.
    """
    dag = WorkflowDAG([WorkflowStage("a", run=_async_stage)])
    out = dag.execute()
    assert out == {"a": "done"}


def test_atomic_write_text_and_binary(tmp_path):
    """Green sanity: supported text and binary modes still work."""
    p = tmp_path / "t.txt"
    atomic_write(p, "hello")
    assert p.read_text() == "hello"
    pb = tmp_path / "b.bin"
    atomic_write(pb, b"\x00\x01", mode="wb")
    assert pb.read_bytes() == b"\x00\x01"
