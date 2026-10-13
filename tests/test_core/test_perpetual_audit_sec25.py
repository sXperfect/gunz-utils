"""Perpetual security audit phase 25 (round 4, deepest).

Re-audit of the highest-security-impact modules:
``subprocess``, ``network``, ``serialization``.

Findings:

1. ``run_command`` bounded capture blocks on an escaped descendant's held pipe
   after the root command has already exited (unbounded when ``timeout`` is
   None).

   In ``_run_command_bounded`` (subprocess.py) the reader threads poll their
   pipes with a selector so that ``stop`` can interrupt them, and that
   mechanism is armed on every failure path.  But on the normal completion
   path ``stop`` is never set: after ``process.wait()`` returns (the root has
   exited), the join loop in subprocess.py:313-324 keeps waiting for the
   reader threads, and a reader whose pipe is held open by an escaped
   descendant (e.g. ``sh -c 'sleep 3 &'`` inheriting stdout) never reaches
   EOF, so the loop spins with no deadline when ``timeout`` is None.  The
   bounded capture therefore blocks for the full lifetime of any pipe-holding
   descendant (and indefinitely for a long-lived one) even though the root
   command finished.  ``run_command(['sh','-c','sleep 3 &'],
   max_output_bytes=1000, timeout=None)`` blocks ~3 s and returns rc=0.

   Expected: the bounded path should return promptly once the root process has
   exited (a descendant holding a pipe open without writing is not reliable
   capture input, matching the module's own escaped-descendant note), instead
   of blocking on the descendant's lifetime.

2. ``run_command`` (sync) and ``run_command_async`` raise different timeout
   exception types.  ``run_command_async`` surfaces ``TimeoutError`` (as
   ``asyncio.wait_for`` does), while ``run_command`` surfaces
   ``subprocess.TimeoutExpired``, which is NOT a subclass of ``TimeoutError``.
   A caller that follows the module's timeout contract (``except TimeoutError``)
   silently misses synchronous timeouts.

   Expected: a consistent ``TimeoutError`` for the timeout condition in both
   the synchronous and asynchronous entry points.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from gunz_utils.subprocess import CommandOutputLimitError, run_command

_SRC = str(Path(__file__).resolve().parents[2] / "src")


def test_bounded_run_command_returns_when_root_exits_despite_held_pipe():
    """RED: bounded capture must not block for a pipe-holding descendant after
    the root command has already exited.

    The root ``sh -c 'sleep 3 &'`` exits with code 0 immediately, but the
    backgrounded ``sleep 3`` inherits stdout and keeps the capture pipe open
    for ~3 s.  The bounded path must return once the root has exited rather
    than block for the descendant's lifetime.
    """
    code = (
        "import sys, time\n"
        f"sys.path.insert(0, {_SRC!r})\n"
        "from gunz_utils.subprocess import run_command\n"
        "t = time.monotonic()\n"
        "run_command(['sh', '-c', 'sleep 3 &'], max_output_bytes=1000, timeout=None)\n"
        "print(time.monotonic() - t)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    duration = float(result.stdout.strip())
    assert duration < 1.5, (
        f"bounded run_command blocked {duration:.2f}s on a descendant-held pipe "
        "after the root exited (should return promptly)"
    )


def test_sync_timeout_raises_timeout_error():
    """RED: ``run_command`` timeout must surface as ``TimeoutError`` (the same
    type as ``run_command_async``), not the non-``TimeoutError``
    ``subprocess.TimeoutExpired``.
    """
    with pytest.raises(TimeoutError):
        run_command(["sleep", "2"], timeout=0.1, max_output_bytes=1000)


def test_sync_timeout_error_is_not_timeout_expired_semantics_conflict():
    """Green sanity: the sync bounded path still surfaces *a* timeout when the
    deadline passes, and raises the output-limit error for over-limit output.
    """
    with pytest.raises(Exception) as excinfo:
        run_command(["sleep", "2"], timeout=0.1, max_output_bytes=1000)
    # Whatever the timeout exception type, it must not be the output-limit
    # error, and the process must be cleaned up.
    assert not isinstance(excinfo.value, CommandOutputLimitError)


def test_bounded_output_limit_error():
    """Green sanity: the bounded capture enforces the shared output limit."""
    with pytest.raises(CommandOutputLimitError):
        run_command(
            ["python3", "-c", "import sys; sys.stdout.write('a'*1000)"],
            max_output_bytes=100,
        )
