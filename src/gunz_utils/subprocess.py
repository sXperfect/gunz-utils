"""Safe synchronous and asynchronous subprocess helpers."""
from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio
import math
import os
import signal
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

    def __init__(self,
        result: CommandResult,
    ) -> None:
        super().__init__(f"command failed with exit code {result.returncode}")
        self.result = result


class CommandOutputLimitError(RuntimeError):
    """Raised when captured command output exceeds the configured limit."""


@dataclass
class _CaptureState:
    total: int = 0
    exceeded: bool = False


def _validate_timeout_value(
    value: float | None,
    *,
    name: str,
) -> float | None:
    """Validate and normalize a timeout value.

    Parameters
    ----------
    value : float or None
        Raw timeout to validate, or ``None`` when unset.
    name : str
        Argument name used in the error message.

    Returns
    -------
    float or None
        The value coerced to ``float``, or ``None`` when the input was ``None``.

    Raises
    ------
    ValueError
        If ``value`` is not a finite non-negative number.
    """
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(float(value))
        or value < 0
    ):
        raise ValueError(f"{name} must be a finite non-negative number or None")
    return float(value)


def _validate_output_limit(
    max_output_bytes: int | None,
) -> None:
    """Validate a captured-output byte limit.

    Parameters
    ----------
    max_output_bytes : int or None
        Output limit to validate, or ``None`` when unbounded.

    Raises
    ------
    ValueError
        If ``max_output_bytes`` is not a non-negative integer.
    """
    if max_output_bytes is None:
        return
    if (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or max_output_bytes < 0
    ):
        raise ValueError("max_output_bytes must be a non-negative integer or None")


def _output_limit_error(
    max_output_bytes: int,
) -> CommandOutputLimitError:
    """Build the error raised when captured output exceeds the limit.

    Parameters
    ----------
    max_output_bytes : int
        The configured output limit.

    Returns
    -------
    CommandOutputLimitError
        A ready-to-raise exception describing the exceeded limit.
    """
    return CommandOutputLimitError(
        f"captured command output exceeded {max_output_bytes} bytes"
    )


def _kill_process(
    process: subprocess.Popen[bytes],
) -> None:
    """Kill a bounded-capture process and its POSIX process group.

    Parameters
    ----------
    process : subprocess.Popen
        The running subprocess to terminate.
    """
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (OSError, ProcessLookupError):
            pass
    if process.poll() is None:
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
    """Drain one pipe while retaining at most the shared output limit.

    Parameters
    ----------
    stream : BinaryIO
        The pipe to drain.
    target : bytearray
        Buffer receiving the retained output.
    process : subprocess.Popen
        Process killed when the limit is exceeded.
    max_output_bytes : int
        Maximum bytes retained across all pipes.
    state : _CaptureState
        Shared running-total and exceeded flag.
    lock : threading.Lock
        Guards ``state`` across concurrent readers.
    errors : list[BaseException]
        Collects reader exceptions for re-raising by the caller.
    """
    try:
        read_chunk = getattr(stream, "read1", stream.read)
        while True:
            chunk = read_chunk(64 * 1024)
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
    """Run a command while streaming stdout/stderr into bounded buffers.

    Parameters
    ----------
    args : Sequence[str]
        Command and arguments to execute without a shell.
    timeout : float or None
        Wall-clock limit before the process is killed.
    cwd : str or None
        Working directory for the child process.
    env : Mapping[str, str] or None
        Extra environment overrides merged over ``os.environ``.
    max_output_bytes : int
        Maximum combined captured output before raising.

    Returns
    -------
    tuple[int, bytes, bytes]
        The exit code, stdout bytes, and stderr bytes.

    Raises
    ------
    CommandOutputLimitError
        If captured output exceeds ``max_output_bytes``.
    """
    process = subprocess.Popen(
        list(args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
        start_new_session=os.name == "posix",
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
    #? --- Execution ---
    timeout: float | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    #? --- Output capture ---
    encoding: str = "utf-8",
    errors: str = "strict",
    max_output_bytes: int | None = None,
) -> CommandResult:
    """Run a command without a shell and capture optionally bounded text output.

    Parameters
    ----------
    args : Sequence[str]
        Command and arguments to execute without a shell.
    timeout : float or None, optional
        Wall-clock limit before the process is killed. Defaults to no limit.
    check : bool, optional
        Raise ``CommandError`` when the exit code is non-zero. Defaults to
        ``False``.
    cwd : str or None, optional
        Working directory for the child process.
    env : Mapping[str, str] or None, optional
        Extra environment overrides merged over ``os.environ``.
    encoding : str, optional
        Text encoding used to decode captured output. Defaults to ``"utf-8"``.
    errors : str, optional
        Decoding error handler. Defaults to ``"strict"``.
    max_output_bytes : int or None, optional
        Maximum combined captured output before raising. Defaults to
        unbounded.

    Returns
    -------
    CommandResult
        The captured result with elapsed wall-clock duration.

    Raises
    ------
    ValueError
        If ``args`` is empty or an option is invalid.
    CommandError
        If ``check`` is true and the exit code is non-zero.
    CommandOutputLimitError
        If captured output exceeds ``max_output_bytes``.
    """
    if not args:
        raise ValueError("args must not be empty")
    timeout = _validate_timeout_value(timeout, name="timeout")
    _validate_output_limit(max_output_bytes)
    started = time.perf_counter()
    if max_output_bytes is None:
        completed = subprocess.run(
            list(args),
            stdin=subprocess.DEVNULL,
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
    """Terminate a process, escalating to SIGKILL after a grace period.

    Parameters
    ----------
    process : asyncio.subprocess.Process
        The running subprocess to stop.
    terminate_grace : float
        Seconds to wait for graceful termination before force-killing.
    """
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
    elif process.returncode is None:
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=terminate_grace)
    except TimeoutError:
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        elif process.returncode is None:
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
    """Drain one async pipe while retaining at most the shared output limit.

    Parameters
    ----------
    stream : asyncio.StreamReader
        The pipe to drain.
    target : bytearray
        Buffer receiving the retained output.
    process : asyncio.subprocess.Process
        Process killed when the limit is exceeded.
    max_output_bytes : int
        Maximum bytes retained across all pipes.
    state : _CaptureState
        Shared running-total and exceeded flag.
    """
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
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        elif process.returncode is None:
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
    """Await a process while streaming output into bounded buffers.

    Parameters
    ----------
    process : asyncio.subprocess.Process
        The running subprocess to communicate with.
    timeout : float or None
        Wall-clock limit before the process is stopped.
    max_output_bytes : int
        Maximum combined captured output before raising.
    terminate_grace : float
        Seconds to wait for graceful termination before force-killing.

    Returns
    -------
    tuple[bytes, bytes]
        The stdout bytes and stderr bytes.

    Raises
    ------
    CommandOutputLimitError
        If captured output exceeds ``max_output_bytes``.
    """
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
        await asyncio.shield(_stop_process(process, terminate_grace=terminate_grace))
        await asyncio.gather(*readers, return_exceptions=True)
        raise
    except BaseException:
        await asyncio.shield(_stop_process(process, terminate_grace=terminate_grace))
        await asyncio.gather(*readers, return_exceptions=True)
        raise

    if state.exceeded:
        raise _output_limit_error(max_output_bytes)
    return bytes(stdout), bytes(stderr)


async def run_command_async(
    args: Sequence[str],
    *,
    #? --- Execution ---
    timeout: float | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    #? --- Output capture ---
    encoding: str = "utf-8",
    errors: str = "strict",
    max_output_bytes: int | None = None,
    #? --- Cleanup ---
    terminate_grace: float = 1.0,
) -> CommandResult:
    """Run a subprocess with graceful cleanup and optionally bounded output.

    Parameters
    ----------
    args : Sequence[str]
        Command and arguments to execute without a shell.
    timeout : float or None, optional
        Wall-clock limit before the process is stopped. Defaults to no limit.
    check : bool, optional
        Raise ``CommandError`` when the exit code is non-zero. Defaults to
        ``False``.
    cwd : str or None, optional
        Working directory for the child process.
    env : Mapping[str, str] or None, optional
        Extra environment overrides merged over ``os.environ``.
    encoding : str, optional
        Text encoding used to decode captured output. Defaults to ``"utf-8"``.
    errors : str, optional
        Decoding error handler. Defaults to ``"strict"``.
    max_output_bytes : int or None, optional
        Maximum combined captured output before raising. Defaults to
        unbounded.
    terminate_grace : float, optional
        Seconds to wait for graceful termination before force-killing.
        Defaults to ``1.0``.

    Returns
    -------
    CommandResult
        The captured result with elapsed wall-clock duration.

    Raises
    ------
    ValueError
        If ``args`` is empty or an option is invalid.
    CommandError
        If ``check`` is true and the exit code is non-zero.
    CommandOutputLimitError
        If captured output exceeds ``max_output_bytes``.
    """
    if not args:
        raise ValueError("args must not be empty")
    timeout = _validate_timeout_value(timeout, name="timeout")
    validated_grace = _validate_timeout_value(
        terminate_grace,
        name="terminate_grace",
    )
    if validated_grace is None:
        raise RuntimeError("validated terminate_grace unexpectedly became None")
    terminate_grace = validated_grace
    _validate_output_limit(max_output_bytes)
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
        start_new_session=os.name == "posix",
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
