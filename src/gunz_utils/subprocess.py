"""Safe synchronous and asynchronous subprocess helpers."""

from __future__ import annotations

import asyncio
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


def run_command(
    args: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    encoding: str = "utf-8",
    errors: str = "strict",
) -> CommandResult:
    """Run a command without invoking a shell and capture text output."""
    if not args:
        raise ValueError("args must not be empty")
    started = time.perf_counter()
    completed = subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        encoding=encoding,
        errors=errors,
        timeout=timeout,
        check=False,
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
    )
    result = CommandResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration=time.perf_counter() - started,
    )
    if check and result.returncode:
        raise CommandError(result)
    return result


async def run_command_async(
    args: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = False,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    encoding: str = "utf-8",
    errors: str = "strict",
) -> CommandResult:
    """Run a subprocess asynchronously without invoking a shell."""
    if not args:
        raise ValueError("args must not be empty")
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
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
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


__all__ = ["CommandError", "CommandResult", "run_command", "run_command_async"]
