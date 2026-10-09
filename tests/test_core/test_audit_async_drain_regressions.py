"""Deterministic finite stream scheduling for async subprocess drain ownership."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Coroutine
from types import CoroutineType
from typing import Any, TypeVar, cast

import pytest

import gunz_utils.subprocess as commands

_T = TypeVar("_T")


class _RecordedTransport(asyncio.Transport):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ControlledProcess:
    def __init__(self, *, exited: bool) -> None:
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.stdout_transport = _RecordedTransport()
        self.stderr_transport = _RecordedTransport()
        self.stdout.set_transport(self.stdout_transport)
        self.stderr.set_transport(self.stderr_transport)
        self.communicate_started = asyncio.Event()
        self.returncode: int | None = 0 if exited else None
        self.pid = 123456789
        self.wait_started = asyncio.Event()
        self.exit = asyncio.Event()
        if exited:
            self.exit.set()

    async def wait(self) -> int:
        self.wait_started.set()
        await self.exit.wait()
        assert self.returncode is not None
        return self.returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        self.communicate_started.set()
        streams = await asyncio.gather(self.stdout.read(), self.stderr.read())
        await self.wait()
        return streams[0], streams[1]

    def close_streams(self) -> None:
        self.stdout.feed_eof()
        self.stderr.feed_eof()


async def _bounded_result(operation: asyncio.Task[_T], timeout: float = 0.15) -> _T:
    done, _ = await asyncio.wait({operation}, timeout=timeout)
    assert operation in done, "subprocess helper exceeded the independent test watchdog"
    return operation.result()


async def _settle(operation: asyncio.Task[object], process: _ControlledProcess) -> None:
    process.close_streams()
    process.returncode = process.returncode if process.returncode is not None else -15
    process.exit.set()
    if not operation.done():
        operation.cancel()
    done, _ = await asyncio.wait({operation}, timeout=0.3)
    assert operation in done, "controlled test task did not settle after finite EOF"
    try:
        operation.result()
    except BaseException:
        pass


def _install_stop(
    monkeypatch: pytest.MonkeyPatch, process: _ControlledProcess
) -> list[str]:
    stops: list[str] = []

    async def stop(
        _process: asyncio.subprocess.Process, *, terminate_grace: float
    ) -> None:
        assert terminate_grace == 0.01
        stops.append("stopped")
        process.returncode = (
            process.returncode if process.returncode is not None else -15
        )
        process.exit.set()

    monkeypatch.setattr(commands, "_stop_process", stop)
    return stops


def _communicate(
    process: _ControlledProcess,
) -> Coroutine[Any, Any, tuple[bytes, bytes]]:
    return commands._communicate_bounded(
        cast(asyncio.subprocess.Process, process),
        timeout=0.01,
        max_output_bytes=64,
        terminate_grace=0.01,
    )


def test_timeout_covers_pipe_drain_after_controlled_process_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=True)
        stops = _install_stop(monkeypatch, process)
        operation = asyncio.create_task(_communicate(process))
        try:
            await asyncio.wait_for(process.wait_started.wait(), timeout=0.15)
            with pytest.raises(TimeoutError):
                await _bounded_result(operation)
            assert stops == ["stopped"]
            assert process.stdout_transport.closed
            assert process.stderr_transport.closed
        finally:
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


def test_cancellation_does_not_wait_for_unowned_pipe_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=False)
        stops = _install_stop(monkeypatch, process)
        operation = asyncio.create_task(_communicate(process))
        try:
            await asyncio.wait_for(process.wait_started.wait(), timeout=0.15)
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await _bounded_result(operation)
            assert stops == ["stopped"]
            assert process.stdout_transport.closed
            assert process.stderr_transport.closed
        finally:
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


@pytest.mark.parametrize("timeout", [None, 0.01])
def test_success_drains_both_streams_with_shared_exact_cap(
    timeout: float | None,
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=True)
        process.stdout.feed_data(b"abc")
        process.stderr.feed_data(b"def")
        process.close_streams()
        result = await commands._communicate_bounded(
            cast(asyncio.subprocess.Process, process),
            timeout=timeout,
            max_output_bytes=6,
            terminate_grace=0.01,
        )
        assert result == (b"abc", b"def")
        assert len(asyncio.all_tasks()) == 1

    asyncio.run(proof())


def test_overflow_does_not_wait_for_other_pipe_without_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=True)
        stops = _install_stop(monkeypatch, process)
        monkeypatch.setattr(commands.os, "killpg", lambda *_args: None, raising=False)
        process.stdout.feed_data(b"over limit")
        operation = asyncio.create_task(
            commands._communicate_bounded(
                cast(asyncio.subprocess.Process, process),
                timeout=None,
                max_output_bytes=3,
                terminate_grace=0.01,
            )
        )
        try:
            with pytest.raises(commands.CommandOutputLimitError):
                await _bounded_result(operation)
            assert stops == ["stopped"]
            assert process.stdout_transport.closed
            assert process.stderr_transport.closed
            assert len(asyncio.all_tasks()) == 1
        finally:
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


def test_reader_error_stops_process_without_waiting_for_other_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=False)
        stops = _install_stop(monkeypatch, process)
        process.stdout.set_exception(OSError("synthetic read failure"))
        operation = asyncio.create_task(_communicate(process))
        try:
            with pytest.raises(OSError, match="synthetic read failure"):
                await _bounded_result(operation)
            assert stops == ["stopped"]
            assert process.stdout_transport.closed
            assert process.stderr_transport.closed
            assert len(asyncio.all_tasks()) == 1
        finally:
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


def test_repeated_cancellation_waits_for_owned_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=False)
        stop_started, release = asyncio.Event(), asyncio.Event()

        async def stop(
            _process: asyncio.subprocess.Process, *, terminate_grace: float
        ) -> None:
            stop_started.set()
            await release.wait()
            process.returncode = -15
            process.exit.set()

        monkeypatch.setattr(commands, "_stop_process", stop)
        operation = asyncio.create_task(_communicate(process))
        try:
            await asyncio.wait_for(process.wait_started.wait(), timeout=0.15)
            operation.cancel()
            await asyncio.wait_for(stop_started.wait(), timeout=0.15)
            operation.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await _bounded_result(operation)
            assert len(asyncio.all_tasks()) == 1
        finally:
            release.set()
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


@pytest.mark.parametrize("failing_coroutine", ["reader", "capture", "failed"])
def test_task_setup_failure_closes_unstarted_coroutine_and_joins_owned_tasks(
    monkeypatch: pytest.MonkeyPatch, failing_coroutine: str
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=False)
        stops = _install_stop(monkeypatch, process)
        original = commands.asyncio.create_task
        failures: list[CoroutineType] = []
        reader_count = 0

        def create(coroutine: Coroutine[Any, Any, Any], **kwargs: Any) -> Any:
            nonlocal reader_count
            native = cast(CoroutineType, coroutine)
            name = native.cr_code.co_name
            if name == "_read_bounded_async_pipe":
                reader_count += 1
            selected = (
                failing_coroutine == "reader"
                and reader_count == 2
                and name == "_read_bounded_async_pipe"
            ) or name == failing_coroutine
            if selected:
                failures.append(native)
                raise RuntimeError("synthetic task setup failure")
            return original(coroutine, **kwargs)

        monkeypatch.setattr(commands.asyncio, "create_task", create)
        operation = original(_communicate(process))
        try:
            with pytest.raises(RuntimeError, match="synthetic task setup failure"):
                await _bounded_result(operation)
            assert stops == ["stopped"]
            assert process.stdout_transport.closed
            assert process.stderr_transport.closed
            assert failures and failures[0].cr_frame is None
            assert len(asyncio.all_tasks()) == 1
        finally:
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


@pytest.mark.parametrize("cancel", [False, True])
def test_unlimited_capture_error_path_closes_owned_pipe_transports(
    monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    async def proof() -> None:
        process = _ControlledProcess(exited=False)
        stops = _install_stop(monkeypatch, process)

        async def spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            return cast(asyncio.subprocess.Process, process)

        monkeypatch.setattr(commands.asyncio, "create_subprocess_exec", spawn)
        operation = asyncio.create_task(
            commands.run_command_async(
                ["synthetic command"], timeout=0.01, terminate_grace=0.01
            )
        )
        try:
            await asyncio.wait_for(process.communicate_started.wait(), timeout=0.15)
            if cancel:
                operation.cancel()
            with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
                await _bounded_result(operation)
            assert stops == ["stopped"]
            assert process.stdout_transport.closed
            assert process.stderr_transport.closed
            assert len(asyncio.all_tasks()) == 1
        finally:
            await _settle(cast(asyncio.Task[object], operation), process)

    asyncio.run(proof())


@pytest.mark.parametrize("limit", [None, 64])
def test_real_finite_child_timeout_reaps_process_and_closes_pipes(
    monkeypatch: pytest.MonkeyPatch, limit: int | None
) -> None:
    async def proof() -> None:
        captured: list[asyncio.subprocess.Process] = []
        original = commands.asyncio.create_subprocess_exec

        async def spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            process = await original(*args, **kwargs)
            captured.append(process)
            return process

        monkeypatch.setattr(commands.asyncio, "create_subprocess_exec", spawn)
        operation = asyncio.create_task(
            commands.run_command_async(
                [sys.executable, "-c", "import time;time.sleep(0.4)"],
                timeout=0.01,
                terminate_grace=0.01,
                max_output_bytes=limit,
            )
        )
        try:
            with pytest.raises(TimeoutError):
                await _bounded_result(operation, timeout=0.8)
            assert len(captured) == 1
            process = captured[0]
            assert process.returncode is not None
            for stream in (process.stdout, process.stderr):
                assert cast(Any, stream)._transport.is_closing()
            if os.name == "posix":
                with pytest.raises(ChildProcessError):
                    os.waitpid(process.pid, os.WNOHANG)
            assert len(asyncio.all_tasks()) == 1
        finally:
            if not operation.done():
                operation.cancel()
            done, _ = await asyncio.wait({operation}, timeout=0.8)
            for process in captured:
                if process.returncode is None:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=0.8)
            assert operation in done
            try:
                operation.result()
            except BaseException:
                pass

    asyncio.run(proof())
