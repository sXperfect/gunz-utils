"""Safe synchronous and asynchronous subprocess helpers."""

from __future__ import annotations

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio
import math
import os
import selectors
import signal
import subprocess
import threading
import time
from collections.abc import Coroutine, Mapping, Sequence
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
        super().__init__(
            f"command failed with exit code {result.returncode}"
        )
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
    """Validate and coerce a finite non-negative timeout value.

    Parameters
    ----------
    value : float or None
        The timeout to validate.
    name : str
        The parameter name, used in error messages.

    Returns
    -------
    float or None
        The coerced finite timeout, or None when the input was None.

    Raises
    ------
    ValueError
        If ``value`` is a bool, not a finite number, or negative.
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
    """Validate a non-negative output limit.

    Parameters
    ----------
    max_output_bytes : int or None
        The output limit to validate.

    Raises
    ------
    ValueError
        If ``max_output_bytes`` is a bool, not an integer, or negative.
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
        A ready-to-raise error describing the exceeded limit.
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
    process : subprocess.Popen[bytes]
        The process to terminate.
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
    stop: threading.Event,
) -> None:
    """Drain one pipe while retaining at most the shared output limit.

    Parameters
    ----------
    stream : BinaryIO
        stream parameter.
    target : bytearray
        target parameter.
    process : subprocess.Popen[bytes]
        process parameter.
    max_output_bytes : int
        max_output_bytes parameter.
    state : _CaptureState
        state parameter.
    lock : threading.Lock
        lock parameter.
    errors : list[BaseException]
        errors parameter.
    stop : threading.Event
        stop parameter.
    """
    try:
        read_chunk = getattr(stream, "read1", stream.read)
        #? POSIX pipe readiness lets cleanup interrupt a silent inherited pipe
        #? even if its holder has escaped the owned process group.
        selector = selectors.DefaultSelector() if os.name == "posix" else None
        try:
            if selector is not None:
                selector.register(stream, selectors.EVENT_READ)
            while not stop.is_set():
                if selector is not None and not selector.select(timeout=0.05):
                    continue
                if stop.is_set():
                    return
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
        finally:
            if selector is not None:
                selector.close()
    except BaseException as exc:
        errors.append(exc)
        _kill_process(process)
    finally:
        stream.close()


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
        args parameter.
    timeout : float | None
        timeout parameter.
    cwd : str | None
        cwd parameter.
    env : Mapping[str, str] | None
        env parameter.
    max_output_bytes : int
        max_output_bytes parameter.

    Returns
    -------
    tuple[int, bytes, bytes]
        The result of the operation.
    """
    deadline = None if timeout is None else time.monotonic() + timeout
    stdout = bytearray()
    stderr = bytearray()
    state = _CaptureState()
    lock = threading.Lock()
    reader_errors: list[BaseException] = []
    stop = threading.Event()
    threads: list[threading.Thread] = []
    started_threads: list[threading.Thread] = []

    def remaining_timeout() -> float | None:
        """remaining_timeout() function.

        Returns
        -------
        float | None
            The result of the operation.
        """
        return None if deadline is None else max(0.0, deadline - time.monotonic())

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

    try:
        if stdout_pipe is None or stderr_pipe is None:
            raise RuntimeError("failed to create subprocess capture pipes")
        for pipe, target in ((stdout_pipe, stdout), (stderr_pipe, stderr)):
            threads.append(
                threading.Thread(
                    target=_read_bounded_pipe,
                    args=(pipe, target, process),
                    kwargs={
                        "max_output_bytes": max_output_bytes,
                        "state": state,
                        "lock": lock,
                        "errors": reader_errors,
                        "stop": stop,
                    },
                    daemon=True,
                )
            )
        for thread in threads:
            thread.start()
            started_threads.append(thread)
        returncode = process.wait(timeout=remaining_timeout())
        for thread in threads:
            while thread.is_alive():
                if state.exceeded:
                    raise _output_limit_error(max_output_bytes)
                if reader_errors:
                    error = RuntimeError("failed while capturing subprocess output")
                    raise error from reader_errors[0]
                remaining = remaining_timeout()
                if remaining is not None and remaining <= 0:
                    raise subprocess.TimeoutExpired(process.args, timeout or 0.0)
                thread.join(timeout=0.05 if remaining is None else min(0.05, remaining))
    except BaseException as exc:
        _kill_process(process)
        stop.set()
        cleanup_deadline = time.monotonic() + 0.5
        try:
            process.wait(timeout=max(0.0, cleanup_deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
        for thread in started_threads:
            thread.join(timeout=max(0.0, cleanup_deadline - time.monotonic()))
        #? Readers own their pipes once started. Never close a buffered stream
        #? from another thread while it may hold the stream's blocking-read lock.
        #? Windows cannot poll anonymous pipes; a descendant outside supported
        #? process cleanup may retain a daemon reader until it closes its pipe.
        for index, cleanup_pipe in enumerate((stdout_pipe, stderr_pipe)):
            if cleanup_pipe is not None and (
                index >= len(threads) or threads[index] not in started_threads
            ):
                try:
                    cleanup_pipe.close()
                except OSError:
                    pass
        if isinstance(exc, subprocess.TimeoutExpired) and state.exceeded:
            raise _output_limit_error(max_output_bytes) from None
        raise
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
    """Run a command without a shell and capture optionally bounded text output.

    Parameters
    ----------
    args : Sequence[str]
        args parameter.
    timeout : float | None
        timeout parameter.
    check : bool
        check parameter.
    cwd : str | None
        cwd parameter.
    env : Mapping[str, str] | None
        env parameter.
    encoding : str
        encoding parameter.
    errors : str
        errors parameter.
    max_output_bytes : int | None
        max_output_bytes parameter.

    Returns
    -------
    CommandResult
        The result of the operation.
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
    """_stop_process() function.

    Parameters
    ----------
    process : asyncio.subprocess.Process
        process parameter.
    terminate_grace : float
        terminate_grace parameter.
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


async def _cleanup_async_process(
    process: asyncio.subprocess.Process,
    tasks: Sequence[asyncio.Task[None]] = (),
    *,
    terminate_grace: float,
) -> None:
    """Join owned tasks and close capture transports before stopping the child.

    Pipe EOF may belong to an escaped descendant. StreamReader exposes no public
    close method; its CPython transport is the owned read end on both supported
    Python versions. Closing it also allows Process.wait to reap independently of
    a foreign pipe writer. Repeated caller cancellation cannot abandon cleanup.
    """

    async def cleanup() -> None:
        for task in tasks:
            task.cancel()
        for stream in (process.stdout, process.stderr):
            transport = getattr(stream, "_transport", None)
            if transport is not None:
                transport.close()
        await asyncio.gather(*tasks, return_exceptions=True)
        await _stop_process(process, terminate_grace=terminate_grace)

    pending = asyncio.create_task(cleanup())
    cancelled = False
    while not pending.done():
        try:
            await asyncio.shield(pending)
        except asyncio.CancelledError:
            cancelled = True
    pending.result()
    if cancelled:
        raise asyncio.CancelledError


async def _read_bounded_async_pipe(
    stream: asyncio.StreamReader,
    target: bytearray,
    process: asyncio.subprocess.Process,
    *,
    max_output_bytes: int,
    state: _CaptureState,
    failure: asyncio.Event,
) -> None:
    """_read_bounded_async_pipe() function.

    Parameters
    ----------
    stream : asyncio.StreamReader
        stream parameter.
    target : bytearray
        target parameter.
    process : asyncio.subprocess.Process
        process parameter.
    max_output_bytes : int
        max_output_bytes parameter.
    state : _CaptureState
        state parameter.
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
        failure.set()
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
    """_communicate_bounded() function.

    Parameters
    ----------
    process : asyncio.subprocess.Process
        process parameter.
    timeout : float | None
        timeout parameter.
    max_output_bytes : int
        max_output_bytes parameter.
    terminate_grace : float
        terminate_grace parameter.

    Returns
    -------
    tuple[bytes, bytes]
        The result of the operation.
    """
    loop = asyncio.get_running_loop()
    deadline = None if timeout is None else loop.time() + timeout
    stdout_pipe = process.stdout
    stderr_pipe = process.stderr
    if stdout_pipe is None or stderr_pipe is None:
        await _cleanup_async_process(process, terminate_grace=terminate_grace)
        raise RuntimeError("failed to create subprocess capture pipes")

    stdout = bytearray()
    stderr = bytearray()
    state = _CaptureState()
    failure = asyncio.Event()
    readers: list[asyncio.Task[None]] = []
    owned: list[asyncio.Task[None]] = []

    def start(
        coroutine: Coroutine[object, object, None],
    ) -> asyncio.Task[None]:
        try:
            task = asyncio.create_task(coroutine)
        except BaseException:
            coroutine.close()
            raise
        owned.append(task)
        return task

    def reader_finished(
        task: asyncio.Task[None],
    ) -> None:
        if not task.cancelled() and task.exception() is not None:
            failure.set()

    async def capture() -> None:
        await process.wait()
        await asyncio.gather(*readers)

    async def failed() -> None:
        await failure.wait()

    try:
        for stream, target in ((stdout_pipe, stdout), (stderr_pipe, stderr)):
            coroutine = _read_bounded_async_pipe(
                stream,
                target,
                process,
                max_output_bytes=max_output_bytes,
                state=state,
                failure=failure,
            )
            task = start(coroutine)
            task.add_done_callback(reader_finished)
            readers.append(task)
        capture_task = start(capture())
        failure_task = start(failed())
        remaining = None if deadline is None else max(0.0, deadline - loop.time())
        done, _ = await asyncio.wait(
            (capture_task, failure_task),
            timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if state.exceeded:
            raise _output_limit_error(max_output_bytes)
        for reader in readers:
            if reader.done() and not reader.cancelled():
                error = reader.exception()
                if error is not None:
                    raise error
        if capture_task not in done:
            raise TimeoutError
        capture_task.result()
    except BaseException:
        await _cleanup_async_process(process, owned, terminate_grace=terminate_grace)
        raise
    else:
        failure_task.cancel()
        await asyncio.gather(failure_task, return_exceptions=True)
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
    """Run a subprocess with graceful cleanup and optionally bounded output.

    Timeout covers process exit and capture-pipe draining after creation.
    Failure/cancellation closes owned read ends and stops the owned child, signaling
    its POSIX process group;
    escaped descendants are outside that group and remain the caller's responsibility.

    Parameters
    ----------
    args : Sequence[str]
        args parameter.
    timeout : float | None
        timeout parameter.
    check : bool
        check parameter.
    cwd : str | None
        cwd parameter.
    env : Mapping[str, str] | None
        env parameter.
    encoding : str
        encoding parameter.
    errors : str
        errors parameter.
    max_output_bytes : int | None
        max_output_bytes parameter.
    terminate_grace : float
        terminate_grace parameter.

    Returns
    -------
    CommandResult
        The result of the operation.
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
            await _cleanup_async_process(process, terminate_grace=terminate_grace)
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
