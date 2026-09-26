"""Linux process-tree resource profiling for arbitrary executables."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


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


def _memory_rollup(path: Path) -> tuple[int | None, int | None]:
    try:
        values: dict[str, int] = {}
        for line in path.read_text().splitlines():
            key, value, *_ = line.split()
            values[key.rstrip(":")] = int(value) * 1024
        pss = values.get("Pss")
        private = values.get("Private_Clean", 0) + values.get("Private_Dirty", 0)
        return pss, private
    except (FileNotFoundError, PermissionError, ValueError):
        return None, None


def _linux_snapshot(
    root_pid: int,
    started: float,
    *,
    memory_detail: str = "pss",
) -> ProcessSample:
    if memory_detail not in {"rss", "pss", "full"}:
        raise ValueError("memory_detail must be rss, pss, or full")
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
        if memory_detail == "rss":
            pss, private = None, None
        else:
            pss, private = _memory_rollup(proc / str(pid) / "smaps_rollup")
            if memory_detail == "pss":
                private = None
        command = stat[1].strip("()")
        user += pid_user
        system += pid_system
        rss += pid_rss
        threads += pid_threads
        minor_faults += int(stat[9])
        major_faults += int(stat[11])
        if pss is None:
            pss_complete = False
        else:
            pss_total += pss
        if private is None:
            private_complete = False
        else:
            private_total += private
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
) -> ProcessProfile:
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

    def peak(name: str) -> int:
        return max((int(getattr(sample, name)) for sample in samples), default=0)

    def optional_peak(name: str) -> int | None:
        values = [getattr(sample, name) for sample in samples]
        known = [int(value) for value in values if value is not None]
        return max(known) if known else None

    return ProcessProfile(
        args=tuple(args),
        returncode=process.returncode or 0,
        wall_seconds=wall,
        peak_rss_bytes=peak("rss_bytes"),
        peak_pss_bytes=optional_peak("pss_bytes"),
        peak_private_bytes=optional_peak("private_bytes"),
        cpu_user_seconds=max((s.cpu_user_seconds for s in samples), default=0.0),
        cpu_system_seconds=max((s.cpu_system_seconds for s in samples), default=0.0),
        read_bytes=peak("read_bytes"),
        write_bytes=peak("write_bytes"),
        peak_process_count=peak("process_count"),
        peak_threads=peak("threads"),
        minor_faults=peak("minor_faults"),
        major_faults=peak("major_faults"),
        voluntary_context_switches=peak("voluntary_context_switches"),
        involuntary_context_switches=peak("involuntary_context_switches"),
        samples=tuple(samples),
    )


__all__ = [
    "ProcessDetail",
    "ProcessProfile",
    "ProcessSample",
    "profile_command",
]
