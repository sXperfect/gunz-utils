"""Linux process-tree resource profiling for arbitrary executables."""

from __future__ import annotations

import math
import os
import subprocess
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..subprocess import _kill_process


@dataclass(frozen=True)
class ProcessDetail:
    """Per-PID resource snapshot retained for lineage analysis."""

    pid: int
    ppid: int
    command: str
    cpu_user_seconds: float
    cpu_system_seconds: float
    rss_bytes: int
    pss_bytes: int | None
    private_bytes: int | None
    threads: int


@dataclass(frozen=True)
class ProcessSample:
    elapsed: float
    process_count: int
    cpu_user_seconds: float
    cpu_system_seconds: float
    rss_bytes: int
    pss_bytes: int | None
    private_bytes: int | None
    read_bytes: int
    write_bytes: int
    threads: int
    minor_faults: int
    major_faults: int
    voluntary_context_switches: int
    involuntary_context_switches: int
    processes: tuple[ProcessDetail, ...]


@dataclass(frozen=True)
class ProcessProfile:
    args: tuple[str, ...]
    returncode: int
    wall_seconds: float
    peak_rss_bytes: int
    peak_pss_bytes: int | None
    peak_private_bytes: int | None
    cpu_user_seconds: float
    cpu_system_seconds: float
    read_bytes: int
    write_bytes: int
    peak_process_count: int
    peak_threads: int
    minor_faults: int
    major_faults: int
    voluntary_context_switches: int
    involuntary_context_switches: int
    samples: tuple[ProcessSample, ...]

    @property
    def average_cpu_cores(self) -> float:
        cpu = self.cpu_user_seconds + self.cpu_system_seconds
        return 0.0 if self.wall_seconds == 0 else cpu / self.wall_seconds

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _ProcessCounters:
    """Monotonic counters retained for one Linux process lifetime."""

    cpu_user_seconds: float
    cpu_system_seconds: float
    read_bytes: int
    write_bytes: int
    minor_faults: int
    major_faults: int
    voluntary_context_switches: int
    involuntary_context_switches: int


_ProcessIdentity = tuple[int, int]


def _merge_process_counters(
    previous: _ProcessCounters | None,
    current: _ProcessCounters,
) -> _ProcessCounters:
    """Keep the greatest observed monotonic value for one process lifetime."""
    if previous is None:
        return current
    return _ProcessCounters(
        cpu_user_seconds=max(previous.cpu_user_seconds, current.cpu_user_seconds),
        cpu_system_seconds=max(previous.cpu_system_seconds, current.cpu_system_seconds),
        read_bytes=max(previous.read_bytes, current.read_bytes),
        write_bytes=max(previous.write_bytes, current.write_bytes),
        minor_faults=max(previous.minor_faults, current.minor_faults),
        major_faults=max(previous.major_faults, current.major_faults),
        voluntary_context_switches=max(
            previous.voluntary_context_switches,
            current.voluntary_context_switches,
        ),
        involuntary_context_switches=max(
            previous.involuntary_context_switches,
            current.involuntary_context_switches,
        ),
    )


def _memory_rollup(path: Path) -> tuple[int | None, int | None]:
    try:
        values: dict[str, int] = {}
        for line in path.read_text().splitlines():
            key, separator, value = line.partition(":")
            if separator and key in {"Pss", "Private_Clean", "Private_Dirty"}:
                values[key] = int(value.split()[0]) * 1024
        pss = values.get("Pss")
        private = (
            values["Private_Clean"] + values["Private_Dirty"]
            if {"Private_Clean", "Private_Dirty"} <= values.keys()
            else None
        )
        return pss, private
    except (
        FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError
    ):
        return None, None


def _parse_proc_stat(text: str) -> tuple[int, str, list[str]]:
    """Parse /proc/<pid>/stat without splitting spaces inside comm."""
    first_space = text.find(" ")
    close_paren = text.rfind(")")
    if first_space <= 0 or close_paren <= first_space + 1:
        raise ValueError("malformed /proc stat record")
    pid = int(text[:first_space])
    if text[first_space + 1] != "(":
        raise ValueError("malformed /proc stat command field")
    command = text[first_space + 2 : close_paren]
    tail = text[close_paren + 1 :].strip().split()
    if len(tail) < 22:
        raise ValueError("truncated /proc stat record")
    fields = [str(pid), f"({command})", *tail]
    return pid, command, fields


def _require_compatible_procfs() -> Path:
    """Reject procfs mounts whose PID numbers address a different namespace."""
    proc = Path("/proc")
    try:
        proc_pid, _command, _fields = _parse_proc_stat(
            (proc / "self" / "stat").read_text(errors="surrogateescape")
        )
    except (OSError, ValueError) as error:
        raise NotImplementedError(
            "process-tree profiling requires readable Linux /proc/self/stat"
        ) from error
    if proc_pid != os.getpid():
        raise NotImplementedError(
            "process-tree profiling requires procfs in the same PID namespace "
            f"(procfs PID {proc_pid}, process PID {os.getpid()})"
        )
    return proc


def _linux_snapshot(
    root_pid: int,
    started: float,
    *,
    memory_detail: str = "pss",
    lifetime_counters: dict[_ProcessIdentity, _ProcessCounters] | None = None,
) -> ProcessSample:
    if memory_detail not in {"rss", "pss", "full"}:
        raise ValueError("memory_detail must be rss, pss, or full")
    proc = _require_compatible_procfs()
    rows: dict[int, tuple[int, list[str]]] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parsed_pid, _command, stat = _parse_proc_stat(
                (entry / "stat").read_text(errors="surrogateescape")
            )
            rows[parsed_pid] = (int(stat[3]), stat)
        except (
            FileNotFoundError,
            ProcessLookupError,
            PermissionError,
            IndexError,
            ValueError,
        ):
            continue

    tree = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _) in rows.items():
            if ppid in tree and pid not in tree:
                tree.add(pid)
                changed = True

    ticks = os.sysconf("SC_CLK_TCK")
    page_size = os.sysconf("SC_PAGE_SIZE")
    details: list[ProcessDetail] = []
    user = system = 0.0
    rss = read_bytes = write_bytes = 0
    pss_total = private_total = 0
    pss_complete = private_complete = True
    threads = minor_faults = major_faults = 0
    voluntary = involuntary = 0

    for pid in sorted(tree):
        row = rows.get(pid)
        if row is None:
            continue
        ppid, stat = row
        pid_user = int(stat[13]) / ticks
        pid_system = int(stat[14]) / ticks
        pid_rss = max(0, int(stat[23])) * page_size
        pid_threads = int(stat[19])
        pid_start_ticks = int(stat[21])
        pid_minor_faults = int(stat[9])
        pid_major_faults = int(stat[11])
        if memory_detail == "rss":
            pss, private = None, None
        else:
            pss, private = _memory_rollup(proc / str(pid) / "smaps_rollup")
            if memory_detail == "pss":
                private = None
        command = stat[1][1:-1]
        user += pid_user
        system += pid_system
        rss += pid_rss
        threads += pid_threads
        minor_faults += pid_minor_faults
        major_faults += pid_major_faults
        if pss is None:
            pss_complete = False
        else:
            pss_total += pss
        if private is None:
            private_complete = False
        else:
            private_total += private
        pid_read_bytes = 0
        pid_write_bytes = 0
        try:
            io_values = {}
            for line in (proc / str(pid) / "io").read_text().splitlines():
                key, value = line.split(":", 1)
                io_values[key] = int(value.strip())
            pid_read_bytes = io_values.get("read_bytes", 0)
            pid_write_bytes = io_values.get("write_bytes", 0)
            read_bytes += pid_read_bytes
            write_bytes += pid_write_bytes
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
            pass

        pid_voluntary = 0
        pid_involuntary = 0
        try:
            for line in (proc / str(pid) / "status").read_text().splitlines():
                if line.startswith("voluntary_ctxt_switches:"):
                    pid_voluntary = int(line.split()[1])
                elif line.startswith("nonvoluntary_ctxt_switches:"):
                    pid_involuntary = int(line.split()[1])
            voluntary += pid_voluntary
            involuntary += pid_involuntary
        except (
            FileNotFoundError,
            ProcessLookupError,
            PermissionError,
            ValueError,
            IndexError,
        ):
            pass

        if lifetime_counters is not None:
            identity = (pid, pid_start_ticks)
            current = _ProcessCounters(
                cpu_user_seconds=pid_user,
                cpu_system_seconds=pid_system,
                read_bytes=pid_read_bytes,
                write_bytes=pid_write_bytes,
                minor_faults=pid_minor_faults,
                major_faults=pid_major_faults,
                voluntary_context_switches=pid_voluntary,
                involuntary_context_switches=pid_involuntary,
            )
            lifetime_counters[identity] = _merge_process_counters(
                lifetime_counters.get(identity),
                current,
            )

        details.append(
            ProcessDetail(
                pid=pid,
                ppid=ppid,
                command=command,
                cpu_user_seconds=pid_user,
                cpu_system_seconds=pid_system,
                rss_bytes=pid_rss,
                pss_bytes=pss,
                private_bytes=private,
                threads=pid_threads,
            )
        )

    return ProcessSample(
        elapsed=time.perf_counter() - started,
        process_count=len(details),
        cpu_user_seconds=user,
        cpu_system_seconds=system,
        rss_bytes=rss,
        pss_bytes=pss_total if pss_complete else None,
        private_bytes=private_total if private_complete else None,
        read_bytes=read_bytes,
        write_bytes=write_bytes,
        threads=threads,
        minor_faults=minor_faults,
        major_faults=major_faults,
        voluntary_context_switches=voluntary,
        involuntary_context_switches=involuntary,
        processes=tuple(details),
    )


def profile_command(
    args: Sequence[str],
    *,
    interval: float = 0.02,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
    memory_detail: str = "pss",
    detailed_memory_every: int = 1,
) -> ProcessProfile:
    """Sample a command's process tree while limiting expensive memory reads.

    Args:
        args: Executable and arguments to launch without a shell.
        interval: Positive delay in seconds between process snapshots.
        cwd: Optional working directory for the command.
        env: Environment overrides merged with the current environment.
        check: Raise if the command exits with a nonzero status.
        memory_detail: ``rss``, ``pss``, or ``full`` (includes private memory).
        detailed_memory_every: Positive integer snapshot cadence for detailed
            memory reads, starting with the first snapshot. Other snapshots
            record RSS and leave PSS and private memory unknown.

    Returns:
        Profile containing observed samples and peak resource measurements.
        Commands that exit before observation may have no samples.
        Sampling failure or interruption kills the command's POSIX process
        group and reaps its root process. Children that create their own session
        are outside that cleanup group. Normal completion follows the root
        command's lifetime; detached descendants may outlive it.

    Raises:
        ValueError: If arguments or sampling options are invalid.
        NotImplementedError: If Linux process information is unavailable or its
            PID namespace differs from the caller's.
        subprocess.CalledProcessError: If ``check`` is true and the command fails.
    """
    if not args:
        raise ValueError("args must not be empty")
    if (
        isinstance(interval, bool)
        or not isinstance(interval, (int, float))
        or not math.isfinite(float(interval))
        or interval <= 0
    ):
        raise ValueError("interval must be a finite positive number")
    if memory_detail not in {"rss", "pss", "full"}:
        raise ValueError("memory_detail must be rss, pss, or full")
    if (
        not isinstance(detailed_memory_every, int)
        or isinstance(detailed_memory_every, bool)
        or detailed_memory_every <= 0
    ):
        raise ValueError("detailed_memory_every must be a positive integer")
    _require_compatible_procfs()
    started = time.perf_counter()
    process = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
        start_new_session=os.name == "posix",
    )
    samples: list[ProcessSample] = []
    lifetime_counters: dict[_ProcessIdentity, _ProcessCounters] = {}
    snapshot_index = 0
    try:
        while process.poll() is None:
            detail = (
                memory_detail
                if snapshot_index % detailed_memory_every == 0
                else "rss"
            )
            sample = _linux_snapshot(
                process.pid,
                started,
                memory_detail=detail,
                lifetime_counters=lifetime_counters,
            )
            if sample.process_count:
                samples.append(sample)
            snapshot_index += 1
            time.sleep(float(interval))
    except BaseException as error:
        # A sampling failure owns the whole launched command, including children
        # still alive after the root exits. Preserve the original failure even
        # if the process disappears during signaling or cannot be reaped.
        try:
            _kill_process(process)
        except BaseException as cleanup_error:
            error.add_note(f"Process cleanup failed: {type(cleanup_error).__name__}")
        try:
            process.wait(timeout=1.0)
        except BaseException as cleanup_error:
            error.add_note(f"Process reap failed: {type(cleanup_error).__name__}")
        raise
    wall = time.perf_counter() - started
    if check and process.returncode:
        raise subprocess.CalledProcessError(process.returncode, list(args))

    def peak(name: str) -> int:
        return max((int(getattr(sample, name)) for sample in samples), default=0)

    def optional_peak(name: str) -> int | None:
        values = [getattr(sample, name) for sample in samples]
        known = [int(value) for value in values if value is not None]
        return max(known) if known else None

    def lifetime_float(name: str, sample_name: str) -> float:
        if lifetime_counters:
            return sum(
                float(getattr(item, name)) for item in lifetime_counters.values()
            )
        return max(
            (float(getattr(sample, sample_name)) for sample in samples),
            default=0.0,
        )

    def lifetime_int(name: str, sample_name: str) -> int:
        if lifetime_counters:
            return sum(int(getattr(item, name)) for item in lifetime_counters.values())
        return peak(sample_name)

    return ProcessProfile(
        args=tuple(args),
        returncode=process.returncode or 0,
        wall_seconds=wall,
        peak_rss_bytes=peak("rss_bytes"),
        peak_pss_bytes=optional_peak("pss_bytes"),
        peak_private_bytes=optional_peak("private_bytes"),
        cpu_user_seconds=lifetime_float("cpu_user_seconds", "cpu_user_seconds"),
        cpu_system_seconds=lifetime_float("cpu_system_seconds", "cpu_system_seconds"),
        read_bytes=lifetime_int("read_bytes", "read_bytes"),
        write_bytes=lifetime_int("write_bytes", "write_bytes"),
        peak_process_count=peak("process_count"),
        peak_threads=peak("threads"),
        minor_faults=lifetime_int("minor_faults", "minor_faults"),
        major_faults=lifetime_int("major_faults", "major_faults"),
        voluntary_context_switches=lifetime_int(
            "voluntary_context_switches",
            "voluntary_context_switches",
        ),
        involuntary_context_switches=lifetime_int(
            "involuntary_context_switches",
            "involuntary_context_switches",
        ),
        samples=tuple(samples),
    )


__all__ = [
    "ProcessDetail",
    "ProcessProfile",
    "ProcessSample",
    "profile_command",
]
