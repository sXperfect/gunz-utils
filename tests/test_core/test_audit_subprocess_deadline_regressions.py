"""Bounded-capture deadlines include inherited pipe lifetime."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

import gunz_utils.subprocess as command_module
from gunz_utils.subprocess import CommandOutputLimitError, run_command


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group cleanup contract")
@pytest.mark.parametrize("escape_group", [False, True])
@pytest.mark.parametrize("output_overflow", [False, True])
def test_deadline_and_overflow_cleanup_with_inherited_pipe_holder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    escape_group: bool,
    output_overflow: bool,
) -> None:
    captured: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen
    pid_file = tmp_path / "descendant.pid"
    baseline_threads = set(threading.enumerate())

    def record_popen(
        *args: Any,
        **kwargs: Any,
    ) -> subprocess.Popen[bytes]:
        process = original_popen(*args, **kwargs)
        captured.append(process)
        return process

    monkeypatch.setattr(command_module.subprocess, "Popen", record_popen)
    parent = (
        "import subprocess,sys,pathlib; "
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'],"
        f"start_new_session={escape_group!r}); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))"
    )
    if output_overflow:
        parent += "; print('x'*100, flush=True)"
    started = time.monotonic()
    try:
        expected = (
            CommandOutputLimitError if output_overflow else subprocess.TimeoutExpired
        )
        with pytest.raises(expected):
            run_command(
                [sys.executable, "-c", parent], timeout=0.3, max_output_bytes=32
            )
        assert time.monotonic() - started < 1.3
        assert pid_file.exists(), (
            "parent must exit after creating inherited pipe holder"
        )
        if not output_overflow:
            assert captured[0].returncode == 0
        with pytest.raises(ChildProcessError):
            os.waitpid(captured[0].pid, os.WNOHANG)
        assert set(threading.enumerate()) == baseline_threads
    finally:
        #? Escaped descendants are outside helper process-group ownership.
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_bounded_capture_success_and_shared_output_cap() -> None:
    result = run_command(
        [
            sys.executable,
            "-c",
            "import sys;sys.stdout.write('abc');sys.stderr.write('def')",
        ],
        timeout=2,
        max_output_bytes=6,
    )
    assert result.stdout == "abc"
    assert result.stderr == "def"
    with pytest.raises(CommandOutputLimitError):
        run_command(
            [
                sys.executable,
                "-c",
                "import sys;sys.stdout.write('abc');sys.stderr.write('def')",
            ],
            timeout=2,
            max_output_bytes=5,
        )


@pytest.mark.parametrize("phase", ["construct", "start"])
@pytest.mark.parametrize("rejected_reader", [1, 2])
def test_reader_setup_failure_closes_pipes_and_reaps_process(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    rejected_reader: int,
) -> None:
    original_start = threading.Thread.start
    original_thread = threading.Thread
    captured: list[subprocess.Popen[bytes]] = []
    original_popen = subprocess.Popen
    baseline_threads = set(threading.enumerate())
    submissions = 0
    failure = RuntimeError(f"reader {phase} rejected")

    def record_popen(
        *args: Any,
        **kwargs: Any,
    ) -> subprocess.Popen[bytes]:
        process = original_popen(*args, **kwargs)
        captured.append(process)
        return process

    def fail_start(
        thread: threading.Thread,
    ) -> None:
        nonlocal submissions
        submissions += 1
        if submissions == rejected_reader:
            raise failure
        original_start(thread)

    def fail_constructor(
        *args: Any,
        **kwargs: Any,
    ) -> threading.Thread:
        nonlocal submissions
        submissions += 1
        if submissions == rejected_reader:
            raise failure
        return original_thread(*args, **kwargs)

    monkeypatch.setattr(command_module.subprocess, "Popen", record_popen)
    if phase == "start":
        monkeypatch.setattr(threading.Thread, "start", fail_start)
    else:
        monkeypatch.setattr(threading, "Thread", fail_constructor)
    with pytest.raises(RuntimeError) as observed:
        run_command(
            [sys.executable, "-c", "import time;time.sleep(10)"],
            timeout=2,
            max_output_bytes=32,
        )
    assert observed.value is failure
    assert captured[0].returncode is not None
    if os.name == "posix":
        with pytest.raises(ChildProcessError):
            os.waitpid(captured[0].pid, os.WNOHANG)
    assert captured[0].stdout is not None and captured[0].stdout.closed
    assert captured[0].stderr is not None and captured[0].stderr.closed
    assert set(threading.enumerate()) == baseline_threads
