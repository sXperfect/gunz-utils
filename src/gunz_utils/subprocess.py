"""Safe synchronous and asynchronous subprocess helpers."""

from __future__ import annotations

import asyncio
import math
import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


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


def _check_output_limit(
    stdout: bytes | str,
    stderr: bytes | str,
    max_output_bytes: int | None,
) -> None:
    if max_output_bytes is None:
        return
    if (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or max_output_bytes < 0
    ):
        raise ValueError(
            "max_output_bytes must be a non-negative integer or None"
        )
    size = len(stdout) + len(stderr)
    if size > max_output_bytes:
        raise CommandOutputLimitError(
            f"captured command output exceeded {max_output_bytes} bytes"
        )


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
    """Run a command without a shell and capture bounded text output."""
    if not args:
        raise ValueError("args must not be empty")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    _check_output_limit(b"", b"", max_output_bytes)
    started = time.perf_counter()
    completed = subprocess.run(
        list(args),
        capture_output=True,
        text=False,
        timeout=timeout,
        check=False,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
    )
    _check_output_limit(completed.stdout, completed.stderr, max_output_bytes)
    result = CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout.decode(encoding, errors),
        stderr=completed.stderr.decode(encoding, errors),
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
    """Run a subprocess with graceful timeout and cancellation cleanup."""
    if not args:
        raise ValueError("args must not be empty")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(float(timeout))
        or timeout < 0
    ):
        raise ValueError(
            "timeout must be a finite non-negative number or None"
        )
    if (
        isinstance(terminate_grace, bool)
        or not isinstance(terminate_grace, (int, float))
        or not math.isfinite(float(terminate_grace))
        or terminate_grace < 0
    ):
        raise ValueError(
            "terminate_grace must be a finite non-negative number"
        )
    _check_output_limit(b"", b"", max_output_bytes)
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
    )
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
    _check_output_limit(stdout_b, stderr_b, max_output_bytes)
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
