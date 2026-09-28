"""Safe synchronous and asynchronous subprocess helpers."""

from __future__ import annotations

import asyncio
import os
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class CommandResult:
    """Captured subprocess result with elapsed wall-clock duration."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration: float


class CommandError(RuntimeError):
    """Raised when a checked command exits unsuccessfully."""

    def __init__(self, result: CommandResult) -> None:
        super().__init__(
            f"command {result.args!r} failed with exit code {result.returncode}"
        )
        self.result = result


class CommandOutputLimitError(RuntimeError):
    """Raised when captured command output exceeds the configured limit."""


@dataclass
class _CaptureState:
    total: int = 0
    exceeded: bool = False


def _validate_output_limit(max_output_bytes: int | None) -> None:
    if max_output_bytes is None:
        return
    if (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or max_output_bytes < 0
    ):
        raise ValueError("max_output_bytes must be a non-negative integer or None")


def _output_limit_error(max_output_bytes: int) -> CommandOutputLimitError:
    return CommandOutputLimitError(
        f"captured command output exceeded {max_output_bytes} bytes"
    )


def _kill_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        process.kill()
    except OSError:
        pass


def _read_bounded_pipe(
    stream: BinaryIO,
    target: bytearray,
    process: subprocess.Popen[bytes],
    *,
    max_output_bytes: int,
    state: _CaptureState,
    lock: threading.Lock,
    errors: list[BaseException],
) -> None:
    """Drain one pipe while retaining at most the shared output limit."""
    try:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                return
            with lock:
                remaining = max_output_bytes - state.total
                if remaining >= len(chunk):
                    target.extend(chunk)
                    state.total += len(chunk)
                    continue
                if remaining > 0:
                    target.extend(chunk[:remaining])
                    state.total += remaining
                state.exceeded = True
            _kill_process(process)
            return
    except BaseException as exc:
        errors.append(exc)
        _kill_process(process)


def _run_command_bounded(
    args: Sequence[str],
    *,
    timeout: float | None,
    cwd: str | None,
    env: Mapping[str, str] | None,
    max_output_bytes: int,
) -> tuple[int, bytes, bytes]:
    """Run a command while streaming stdout/stderr into bounded buffers."""
    process = subprocess.Popen(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
    )
    stdout_pipe = process.stdout
    stderr_pipe = process.stderr
    if stdout_pipe is None or stderr_pipe is None:
        _kill_process(process)
        process.wait()
        raise RuntimeError("failed to create subprocess capture pipes")

    stdout = bytearray()
    stderr = bytearray()
    state = _CaptureState()
    lock = threading.Lock()
    reader_errors: list[BaseException] = []
    threads = [
        threading.Thread(
            target=_read_bounded_pipe,
            args=(stdout_pipe, stdout, process),
            kwargs={
                "max_output_bytes": max_output_bytes,
                "state": state,
                "lock": lock,
                "errors": reader_errors,
            },
            daemon=True,
        ),
        threading.Thread(
            target=_read_bounded_pipe,
            args=(stderr_pipe, stderr, process),
            kwargs={
                "max_output_bytes": max_output_bytes,
                "state": state,
                "lock": lock,
                "errors": reader_errors,
            },
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process(process)
        process.wait()
        for thread in threads:
            thread.join()
        stdout_pipe.close()
        stderr_pipe.close()
        raise

    for thread in threads:
        thread.join()
    stdout_pipe.close()
    stderr_pipe.close()
    if reader_errors:
        error = RuntimeError("failed while capturing subprocess output")
        raise error from reader_errors[0]
    if state.exceeded:
        raise _output_limit_error(max_output_bytes)
    return returncode, bytes(stdout), bytes(stderr)


def run_command(
    args: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    encoding: str = "utf-8",
    errors: str = "strict",
    max_output_bytes: int | None = None,
) -> CommandResult:
    """Run a command without a shell and capture optionally bounded text output."""
    if not args:
        raise ValueError("args must not be empty")
    _validate_output_limit(max_output_bytes)
    started = time.perf_counter()
    if max_output_bytes is None:
        completed = subprocess.run(
            list(args),
            capture_output=True,
            text=False,
            timeout=timeout,
            check=False,
            cwd=cwd,
            env=None if env is None else {**os.environ, **env},
        )
        returncode = completed.returncode
        stdout_b = completed.stdout
        stderr_b = completed.stderr
    else:
        returncode, stdout_b, stderr_b = _run_command_bounded(
            args,
            timeout=timeout,
            cwd=cwd,
            env=env,
            max_output_bytes=max_output_bytes,
        )

    result = CommandResult(
        args=tuple(args),
        returncode=returncode,
        stdout=stdout_b.decode(encoding, errors),
        stderr=stderr_b.decode(encoding, errors),
        duration=time.perf_counter() - started,
    )
    if check and result.returncode:
        raise CommandError(result)
    return result


async def _stop_process(
    process: asyncio.subprocess.Process,
    *,
    terminate_grace: float,
) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=terminate_grace)
    except TimeoutError:
        process.kill()
        await process.wait()


async def _read_bounded_async_pipe(
    stream: asyncio.StreamReader,
    target: bytearray,
    process: asyncio.subprocess.Process,
    *,
    max_output_bytes: int,
    state: _CaptureState,
) -> None:
    while True:
        chunk = await stream.read(64 * 1024)
        if not chunk:
            return
        remaining = max_output_bytes - state.total
        if remaining >= len(chunk):
            target.extend(chunk)
            state.total += len(chunk)
            continue
        if remaining > 0:
            target.extend(chunk[:remaining])
            state.total += remaining
        state.exceeded = True
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        return


async def _communicate_bounded(
    process: asyncio.subprocess.Process,
    *,
    timeout: float | None,
    max_output_bytes: int,
    terminate_grace: float,
) -> tuple[bytes, bytes]:
    stdout_pipe = process.stdout
    stderr_pipe = process.stderr
    if stdout_pipe is None or stderr_pipe is None:
        await _stop_process(process, terminate_grace=terminate_grace)
        raise RuntimeError("failed to create subprocess capture pipes")

    stdout = bytearray()
    stderr = bytearray()
    state = _CaptureState()
    readers = [
        asyncio.create_task(
            _read_bounded_async_pipe(
                stdout_pipe,
                stdout,
                process,
                max_output_bytes=max_output_bytes,
                state=state,
            )
        ),
        asyncio.create_task(
            _read_bounded_async_pipe(
                stderr_pipe,
                stderr,
                process,
                max_output_bytes=max_output_bytes,
                state=state,
            )
        ),
    ]
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        await asyncio.gather(*readers)
    except (TimeoutError, asyncio.CancelledError):
        await asyncio.shield(
            _stop_process(process, terminate_grace=terminate_grace)
        )
        await asyncio.gather(*readers, return_exceptions=True)
        raise
    except BaseException:
        await asyncio.shield(
            _stop_process(process, terminate_grace=terminate_grace)
        )
        await asyncio.gather(*readers, return_exceptions=True)
        raise

    if state.exceeded:
        raise _output_limit_error(max_output_bytes)
    return bytes(stdout), bytes(stderr)


async def run_command_async(
    args: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    encoding: str = "utf-8",
    errors: str = "strict",
    max_output_bytes: int | None = None,
    terminate_grace: float = 1.0,
) -> CommandResult:
    """Run a subprocess with graceful cleanup and optionally bounded output."""
    if not args:
        raise ValueError("args must not be empty")
    if terminate_grace < 0:
        raise ValueError("terminate_grace must be non-negative")
    _validate_output_limit(max_output_bytes)
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
    )
    if max_output_bytes is None:
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except (TimeoutError, asyncio.CancelledError):
            await asyncio.shield(
                _stop_process(process, terminate_grace=terminate_grace)
            )
            raise
    else:
        stdout_b, stderr_b = await _communicate_bounded(
            process,
            timeout=timeout,
            max_output_bytes=max_output_bytes,
            terminate_grace=terminate_grace,
        )

    result = CommandResult(
        args=tuple(args),
        returncode=process.returncode or 0,
        stdout=stdout_b.decode(encoding, errors),
        stderr=stderr_b.decode(encoding, errors),
        duration=time.perf_counter() - started,
    )
    if check and result.returncode:
        raise CommandError(result)
    return result


__all__ = [
    "CommandError",
    "CommandOutputLimitError",
    "CommandResult",
    "run_command",
    "run_command_async",
]
