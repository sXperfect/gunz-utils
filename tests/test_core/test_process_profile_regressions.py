"""Procfs identity, measurement, and owned-process cleanup regressions."""

from __future__ import annotations

import asyncio
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import gunz_utils.benchmark.process as process_module


def _stat(pid: int, ppid: int = 1, command: bytes = b"worker") -> bytes:
    """A fixed Linux stat record with known CPU, thread, and RSS fields."""
    return (
        str(pid).encode()
        + b" ("
        + command
        + b") S "
        + str(ppid).encode()
        + b" 0 0 0 0 0 7 0 9 0 11 13 0 0 0 0 4 0 12345 0 5\n"
    )


@pytest.fixture
def procfs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a deterministic procfs tree without depending on host PIDs."""
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self" / "stat").write_bytes(_stat(os.getpid()))
    monkeypatch.setattr(process_module, "Path", lambda _path: proc)
    return proc


def test_procfs_namespace_mismatch_prevents_launch(procfs: Path) -> None:
    (procfs / "self" / "stat").write_bytes(_stat(os.getpid() + 1000))
    with patch.object(process_module.subprocess, "Popen") as launch:
        with pytest.raises(NotImplementedError, match="same PID namespace"):
            process_module.profile_command(["command"])
    launch.assert_not_called()


@pytest.mark.parametrize("unavailable", ["missing", "malformed", "unreadable"])
def test_unavailable_procfs_prevents_launch(
    procfs: Path,
    unavailable: str,
) -> None:
    stat = procfs / "self" / "stat"
    if unavailable == "missing":
        stat.unlink()
    elif unavailable == "malformed":
        stat.write_bytes(b"not a stat record")
    else:
        stat.unlink()
        # A directory fails to read without relying on root-sensitive chmod.
        stat.mkdir()
    with patch.object(process_module.subprocess, "Popen") as launch:
        with pytest.raises(NotImplementedError, match="readable Linux"):
            process_module.profile_command(["command"])
    launch.assert_not_called()


def test_snapshot_also_rejects_foreign_pid_namespace(procfs: Path) -> None:
    (procfs / "self" / "stat").write_bytes(_stat(os.getpid() + 1000))
    with pytest.raises(NotImplementedError, match="same PID namespace"):
        process_module._linux_snapshot(123, 0.0)


def test_non_utf8_command_is_kept_in_process_tree(procfs: Path) -> None:
    for pid, ppid, command in (
        (9001, 1, b"root"),
        (9002, 9001, b"worker (\xff)"),
        (9003, 1, b"unrelated"),
    ):
        directory = procfs / str(pid)
        directory.mkdir()
        (directory / "stat").write_bytes(_stat(pid, ppid, command))
    sample = process_module._linux_snapshot(9001, 0.0, memory_detail="rss")
    assert [detail.pid for detail in sample.processes] == [9001, 9002]
    assert (
        sample.processes[1].command.encode(errors="surrogateescape") == b"worker (\xff)"
    )
    assert sample.process_count == 2
    assert sample.threads == 8
    assert sample.rss_bytes == 10 * os.sysconf("SC_PAGE_SIZE")


@pytest.mark.parametrize(
    ("fields", "expected_private"),
    [
        ("", None),
        ("Private_Clean: 3 kB\n", None),
        ("Private_Dirty: 4 kB\n", None),
        ("Private_Clean: 0 kB\nPrivate_Dirty: 0 kB\n", 0),
        ("Private_Clean: 3 kB\nPrivate_Dirty: 4 kB\n", 7 * 1024),
    ],
)
def test_private_memory_requires_complete_fields(
    tmp_path: Path,
    fields: str,
    expected_private: int | None,
) -> None:
    rollup = tmp_path / "smaps_rollup"
    rollup.write_text("Pss: 12 kB\n" + fields)
    assert process_module._memory_rollup(rollup) == (12 * 1024, expected_private)


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("sampling failed"),
        KeyboardInterrupt(),
        SystemExit(17),
        asyncio.CancelledError(),
    ],
)
def test_sampling_failure_preserves_original_and_reaps_group(
    procfs: Path,
    failure: BaseException,
) -> None:
    process = Mock(pid=12345, returncode=None)
    process.poll.return_value = None
    with (
        patch.object(
            process_module.subprocess, "Popen", return_value=process
        ) as launch,
        patch.object(process_module, "_linux_snapshot", side_effect=failure),
        patch.object(process_module, "_kill_process") as kill,
    ):
        with pytest.raises(type(failure)) as caught:
            process_module.profile_command(["command"])
    assert caught.value is failure
    assert launch.call_args.kwargs["start_new_session"] == (os.name == "posix")
    kill.assert_called_once_with(process)
    process.wait.assert_called_once_with(timeout=1.0)


def test_sampling_error_survives_cleanup_errors(procfs: Path) -> None:
    failure = RuntimeError("sampling failed")
    process = Mock(pid=12345, returncode=None)
    process.poll.return_value = None
    process.wait.side_effect = subprocess.TimeoutExpired(["command"], 1.0)
    with (
        patch.object(process_module.subprocess, "Popen", return_value=process),
        patch.object(process_module, "_linux_snapshot", side_effect=failure),
        patch.object(process_module, "_kill_process", side_effect=PermissionError),
    ):
        with pytest.raises(RuntimeError) as caught:
            process_module.profile_command(["command"])
    assert caught.value is failure
    assert caught.value.__notes__ == [
        "Process cleanup failed: PermissionError",
        "Process reap failed: TimeoutExpired",
    ]
    process.wait.assert_called_once_with(timeout=1.0)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group signaling required")
def test_process_exit_during_cleanup_preserves_failure(procfs: Path) -> None:
    failure = RuntimeError("sampling failed")
    process = Mock(pid=12345, returncode=None)
    process.poll.return_value = None
    process.kill.side_effect = ProcessLookupError
    with (
        patch.object(process_module.subprocess, "Popen", return_value=process),
        patch.object(process_module, "_linux_snapshot", side_effect=failure),
        patch.object(os, "killpg", side_effect=ProcessLookupError),
    ):
        with pytest.raises(RuntimeError) as caught:
            process_module.profile_command(["command"])
    assert caught.value is failure
    process.kill.assert_called_once()
    process.wait.assert_called_once_with(timeout=1.0)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group signaling required")
def test_failed_observation_kills_live_descendant(procfs: Path) -> None:
    """Pipe EOF proves the actual child died without relying on procfs access."""
    failure = RuntimeError("injected sampling failure")
    popen = subprocess.Popen
    launched: list[subprocess.Popen[bytes]] = []
    requested_sessions: list[bool] = []

    def launch(args: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        requested_sessions.append(bool(kwargs.get("start_new_session")))
        # Keep cleanup safe even when testing an older implementation that did
        # not request its own session. The requested flag is asserted below.
        kwargs["start_new_session"] = True
        process = popen(args, stdout=subprocess.PIPE, **kwargs)
        launched.append(process)
        return process

    def fail_when_child_ready(*_args: object, **_kwargs: object) -> None:
        stdout = launched[0].stdout
        assert stdout is not None
        assert select.select([stdout], [], [], 3.0)[0], "child failed to become ready"
        assert stdout.readline() == b"ready\n"
        raise failure

    child = "import time;print('ready',flush=True);time.sleep(60)"
    command = (
        "import subprocess,sys;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]).wait()"
    )
    try:
        with (
            patch.object(process_module.subprocess, "Popen", side_effect=launch),
            patch.object(
                process_module, "_linux_snapshot", side_effect=fail_when_child_ready
            ),
        ):
            with pytest.raises(RuntimeError) as caught:
                process_module.profile_command([sys.executable, "-c", command])
        assert caught.value is failure
        assert requested_sessions == [True]
        process = launched[0]
        assert process.returncode is not None
        stdout = process.stdout
        assert stdout is not None
        assert select.select([stdout], [], [], 3.0)[0], "descendant survived cleanup"
        assert stdout.read(1) == b""
    finally:
        for process in launched:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=3.0)
            if process.stdout is not None:
                process.stdout.close()
