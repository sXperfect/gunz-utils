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


@dataclass(frozen=True)
class ProcessProfile:
    """Completed command profile including time-series process-tree samples."""

    args: tuple[str, ...]
    returncode: int
    wall_seconds: float
    peak_rss_bytes: int
    cpu_user_seconds: float
    cpu_system_seconds: float
    read_bytes: int
    write_bytes: int
    samples: tuple[ProcessSample, ...]

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
    live = 0
    for pid in tree:
        row = rows.get(pid)
        if row is None:
            continue
        _, stat = row
        live += 1
        user += int(stat[13]) / ticks
        system += int(stat[14]) / ticks
        rss += max(0, int(stat[23])) * page_size
        minor_faults += int(stat[9])
        major_faults += int(stat[11])
        threads += int(stat[19])
        try:
            io_values = {}
            for line in (proc / str(pid) / "io").read_text().splitlines():
                key, value = line.split(":", 1)
                io_values[key] = int(value.strip())
            read_bytes += io_values.get("read_bytes", 0)
            write_bytes += io_values.get("write_bytes", 0)
        except (FileNotFoundError, PermissionError, ValueError):
            pass
    return ProcessSample(
        elapsed=time.perf_counter() - started,
        process_count=live,
        cpu_user_seconds=user,
        cpu_system_seconds=system,
        rss_bytes=rss,
        read_bytes=read_bytes,
        write_bytes=write_bytes,
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
    peak_rss = max((sample.rss_bytes for sample in samples), default=0)
    user = max((sample.cpu_user_seconds for sample in samples), default=0.0)
    system = max((sample.cpu_system_seconds for sample in samples), default=0.0)
    read_bytes = max((sample.read_bytes for sample in samples), default=0)
    write_bytes = max((sample.write_bytes for sample in samples), default=0)
    return ProcessProfile(
        args=tuple(args),
        returncode=process.returncode or 0,
        wall_seconds=wall,
        peak_rss_bytes=peak_rss,
        cpu_user_seconds=user,
        cpu_system_seconds=system,
        read_bytes=read_bytes,
        write_bytes=write_bytes,
        samples=tuple(samples),
    )


__all__ = ["ProcessProfile", "ProcessSample", "profile_command"]
