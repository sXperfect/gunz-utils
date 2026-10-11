"""Lifetime counter accounting for sampled process trees."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import Mock, patch

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

import gunz_utils.benchmark.process as process_module


def _stat(
    pid: int,
    ppid: int,
    *,
    start_ticks: int,
    user_ticks: int = 11,
    system_ticks: int = 13,
) -> str:
    return (
        f"{pid} (worker) S {ppid} 0 0 0 0 0 7 0 9 0 "
        f"{user_ticks} {system_ticks} 0 0 0 0 4 0 {start_ticks} 0 5\n"
    )


def _sample(
    *,
    cpu_user: float,
    cpu_system: float,
    read_bytes: int,
    write_bytes: int,
    minor_faults: int,
    major_faults: int,
    voluntary: int,
    involuntary: int,
) -> process_module.ProcessSample:
    return process_module.ProcessSample(
        elapsed=0.1,
        process_count=1,
        cpu_user_seconds=cpu_user,
        cpu_system_seconds=cpu_system,
        rss_bytes=1024,
        pss_bytes=None,
        private_bytes=None,
        read_bytes=read_bytes,
        write_bytes=write_bytes,
        threads=1,
        minor_faults=minor_faults,
        major_faults=major_faults,
        voluntary_context_switches=voluntary,
        involuntary_context_switches=involuntary,
        processes=(),
    )


def test_snapshot_uses_pid_and_start_time_as_process_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self" / "stat").write_text(
        _stat(os.getpid(), 1, start_ticks=1),
        encoding="utf-8",
    )
    for pid, ppid, start_ticks in ((9001, 1, 100), (9002, 9001, 200)):
        directory = proc / str(pid)
        directory.mkdir()
        (directory / "stat").write_text(
            _stat(pid, ppid, start_ticks=start_ticks),
            encoding="utf-8",
        )

    monkeypatch.setattr(process_module, "Path", lambda _path: proc)
    lifetime: dict[
        process_module._ProcessIdentity,
        process_module._ProcessCounters,
    ] = {}

    process_module._linux_snapshot(
        9001,
        0.0,
        memory_detail="rss",
        lifetime_counters=lifetime,
    )
    assert (9001, 100) in lifetime
    assert (9002, 200) in lifetime

    (proc / "9002" / "stat").write_text(
        _stat(9002, 9001, start_ticks=300),
        encoding="utf-8",
    )
    process_module._linux_snapshot(
        9001,
        0.0,
        memory_detail="rss",
        lifetime_counters=lifetime,
    )

    assert set(lifetime) == {(9001, 100), (9002, 200), (9002, 300)}


def test_profile_retains_exited_children_and_separates_reused_pids() -> None:
    process = Mock(pid=10, returncode=0)
    process.poll.side_effect = [None, None, None, 0]
    snapshot_index = 0

    def record(
        lifetime: dict[
            process_module._ProcessIdentity,
            process_module._ProcessCounters,
        ],
        identity: process_module._ProcessIdentity,
        counters: process_module._ProcessCounters,
    ) -> None:
        lifetime[identity] = process_module._merge_process_counters(
            lifetime.get(identity),
            counters,
        )

    def fake_snapshot(
        _root_pid: int,
        _started: float,
        *,
        memory_detail: str,
        lifetime_counters: dict[
            process_module._ProcessIdentity,
            process_module._ProcessCounters,
        ],
    ) -> process_module.ProcessSample:
        nonlocal snapshot_index
        snapshot_index += 1
        assert memory_detail == "pss"
        if snapshot_index == 1:
            record(
                lifetime_counters,
                (10, 100),
                process_module._ProcessCounters(1.0, 0.5, 10, 11, 1, 2, 3, 4),
            )
            record(
                lifetime_counters,
                (20, 200),
                process_module._ProcessCounters(4.0, 1.0, 40, 41, 4, 5, 6, 7),
            )
            return _sample(
                cpu_user=5.0,
                cpu_system=1.5,
                read_bytes=50,
                write_bytes=52,
                minor_faults=5,
                major_faults=7,
                voluntary=9,
                involuntary=11,
            )
        if snapshot_index == 2:
            record(
                lifetime_counters,
                (10, 100),
                process_module._ProcessCounters(2.0, 0.75, 20, 21, 2, 3, 4, 5),
            )
            record(
                lifetime_counters,
                (20, 300),
                process_module._ProcessCounters(7.0, 2.0, 70, 71, 7, 8, 9, 10),
            )
            return _sample(
                cpu_user=9.0,
                cpu_system=2.75,
                read_bytes=90,
                write_bytes=92,
                minor_faults=9,
                major_faults=11,
                voluntary=13,
                involuntary=15,
            )

        record(
            lifetime_counters,
            (10, 100),
            process_module._ProcessCounters(3.0, 1.0, 30, 31, 3, 4, 5, 6),
        )
        return _sample(
            cpu_user=3.0,
            cpu_system=1.0,
            read_bytes=30,
            write_bytes=31,
            minor_faults=3,
            major_faults=4,
            voluntary=5,
            involuntary=6,
        )

    with (
        patch.object(process_module, "_require_compatible_procfs"),
        patch.object(process_module.subprocess, "Popen", return_value=process),
        patch.object(process_module, "_linux_snapshot", side_effect=fake_snapshot),
        patch.object(process_module.time, "sleep"),
    ):
        profile = process_module.profile_command(["command"])

    assert profile.cpu_user_seconds == 14.0
    assert profile.cpu_system_seconds == 4.0
    assert profile.read_bytes == 140
    assert profile.write_bytes == 143
    assert profile.minor_faults == 14
    assert profile.major_faults == 17
    assert profile.voluntary_context_switches == 20
    assert profile.involuntary_context_switches == 23
