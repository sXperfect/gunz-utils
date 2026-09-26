"""Linux process-tree resource profiling for arbitrary executables."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class ProcessSample:
    """One aggregate sample across a root process and live descendants."""

    elapsed: float
    process_count: int
    cpu_user_seconds: float
    cpu_system_seconds: float
    rss_bytes: int
    read_bytes: int
    write_bytes: int
    threads: int
    minor_faults: int
    major_faults: int
    voluntary_context_switches: int
    involuntary_context_switches: int


@dataclass(frozen=True)
class ProcessProfile:
    """Completed command profile including process-tree resource samples."""

    args: tuple[str, ...]
    returncode: int
    wall_seconds: float
    peak_rss_bytes: int
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
        """Average aggregate CPU utilization expressed as occupied cores."""
        cpu = self.cpu_user_seconds + self.cpu_system_seconds
        return 0.0 if self.wall_seconds == 0 else cpu / self.wall_seconds

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _linux_snapshot(root_pid: int, started: float) -> ProcessSample:
    proc = Path("/proc")
    if not proc.exists():
        raise NotImplementedError("process-tree profiling currently requires Linux")
    rows: dict[int, tuple[int, list[str]]] = {}
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text().split()
            rows[int(entry.name)] = (int(stat[3]), stat)
        except (FileNotFoundError, PermissionError, IndexError, ValueError):
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
    user = system = 0.0
    rss = read_bytes = write_bytes = 0
    threads = minor_faults = major_faults = 0
    voluntary = involuntary = 0
    live = 0
    for pid in tree:
        row = rows.get(pid)
        if row is None:
            continue
        _, stat = row
        live += 1
        user += int(stat[13]) / ticks
        system += int(stat[14]) / ticks
        minor_faults += int(stat[9])
        major_faults += int(stat[11])
        threads += int(stat[19])
        rss += max(0, int(stat[23])) * page_size
        try:
            io_values = {}
            for line in (proc / str(pid) / "io").read_text().splitlines():
                key, value = line.split(":", 1)
                io_values[key] = int(value.strip())
            read_bytes += io_values.get("read_bytes", 0)
            write_bytes += io_values.get("write_bytes", 0)
        except (FileNotFoundError, PermissionError, ValueError):
            pass
        try:
            for line in (proc / str(pid) / "status").read_text().splitlines():
                if line.startswith("voluntary_ctxt_switches:"):
                    voluntary += int(line.split()[1])
                elif line.startswith("nonvoluntary_ctxt_switches:"):
                    involuntary += int(line.split()[1])
        except (FileNotFoundError, PermissionError, ValueError, IndexError):
            pass
    return ProcessSample(
        elapsed=time.perf_counter() - started,
        process_count=live,
        cpu_user_seconds=user,
        cpu_system_seconds=system,
        rss_bytes=rss,
        read_bytes=read_bytes,
        write_bytes=write_bytes,
        threads=threads,
        minor_faults=minor_faults,
        major_faults=major_faults,
        voluntary_context_switches=voluntary,
        involuntary_context_switches=involuntary,
    )


def profile_command(
    args: Sequence[str],
    *,
    interval: float = 0.02,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> ProcessProfile:
    """Profile a native command and its live descendant process tree on Linux."""
    if not args:
        raise ValueError("args must not be empty")
    if interval <= 0:
        raise ValueError("interval must be positive")
    started = time.perf_counter()
    process = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=None if env is None else {**os.environ, **env},
    )
    samples: list[ProcessSample] = []
    while process.poll() is None:
        samples.append(_linux_snapshot(process.pid, started))
        time.sleep(interval)
    samples.append(_linux_snapshot(process.pid, started))
    wall = time.perf_counter() - started
    if check and process.returncode:
        raise subprocess.CalledProcessError(process.returncode, list(args))

    def peak(name: str, default: int | float = 0) -> int | float:
        return max((getattr(sample, name) for sample in samples), default=default)

    return ProcessProfile(
        args=tuple(args),
        returncode=process.returncode or 0,
        wall_seconds=wall,
        peak_rss_bytes=int(peak("rss_bytes")),
        cpu_user_seconds=float(peak("cpu_user_seconds", 0.0)),
        cpu_system_seconds=float(peak("cpu_system_seconds", 0.0)),
        read_bytes=int(peak("read_bytes")),
        write_bytes=int(peak("write_bytes")),
        peak_process_count=int(peak("process_count")),
        peak_threads=int(peak("threads")),
        minor_faults=int(peak("minor_faults")),
        major_faults=int(peak("major_faults")),
        voluntary_context_switches=int(peak("voluntary_context_switches")),
        involuntary_context_switches=int(peak("involuntary_context_switches")),
        samples=tuple(samples),
    )


__all__ = ["ProcessProfile", "ProcessSample", "profile_command"]
