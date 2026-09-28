"""Optional Linux perf integration for native profiling."""

from __future__ import annotations

import csv
import math
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PerfCounter:
    """One parsed perf-stat counter."""

    event: str
    value: float | None
    unit: str | None


@dataclass(frozen=True)
class PerfStatResult:
    """Structured perf-stat output for one command."""

    args: tuple[str, ...]
    returncode: int
    counters: tuple[PerfCounter, ...]


def perf_available() -> bool:
    """Return whether the Linux perf executable is available."""
    return shutil.which("perf") is not None


def perf_stat(
    args: Sequence[str],
    *,
    events: Sequence[str] = (
        "cycles",
        "instructions",
        "branches",
        "branch-misses",
        "cache-references",
        "cache-misses",
        "page-faults",
        "context-switches",
        "cpu-migrations",
    ),
    cwd: str | None = None,
) -> PerfStatResult:
    """Run a command under perf stat and parse machine-readable counters."""
    if not args:
        raise ValueError("args must not be empty")
    if any(not isinstance(event, str) or not event for event in events):
        raise ValueError("events must contain non-empty strings")
    if not perf_available():
        raise RuntimeError("Linux perf is not installed or not on PATH")
    with tempfile.NamedTemporaryFile() as output:
        command = [
            "perf",
            "stat",
            "-x",
            ",",
            "-o",
            output.name,
        ]
        for event in events:
            command.extend(["-e", event])
        command.extend(["--", *args])
        completed = subprocess.run(command, cwd=cwd, check=False)
        output.seek(0)
        text = output.read().decode("utf-8", "replace")

    counters: list[PerfCounter] = []
    for row in csv.reader(text.splitlines()):
        if len(row) < 3:
            continue
        raw_value = row[0].strip()
        unit = row[1].strip() or None
        event = row[2].strip()
        try:
            parsed = float(raw_value.replace(",", ""))
            value = parsed if math.isfinite(parsed) else None
        except ValueError:
            value = None
        counters.append(PerfCounter(event=event, value=value, unit=unit))
    return PerfStatResult(
        args=tuple(args),
        returncode=completed.returncode,
        counters=tuple(counters),
    )


def perf_record(
    args: Sequence[str],
    output: str | Path,
    *,
    frequency: int = 99,
    call_graph: str = "dwarf",
    cwd: str | None = None,
) -> int:
    """Record perf samples suitable for later perf-script/flamegraph use."""
    if not args:
        raise ValueError("args must not be empty")
    if isinstance(frequency, bool) or not isinstance(frequency, int) or frequency < 1:
        raise ValueError("frequency must be a positive integer")
    if not isinstance(call_graph, str) or not call_graph:
        raise ValueError("call_graph must be a non-empty string")
    if not perf_available():
        raise RuntimeError("Linux perf is not installed or not on PATH")
    completed = subprocess.run(
        [
            "perf",
            "record",
            "-F",
            str(frequency),
            "--call-graph",
            call_graph,
            "-o",
            str(output),
            "--",
            *args,
        ],
        cwd=cwd,
        check=False,
    )
    return completed.returncode


def perf_script(
    data: str | Path,
    output: str | Path,
    *,
    cwd: str | None = None,
) -> None:
    """Export perf.data into perf-script text for external flamegraph tooling."""
    if not perf_available():
        raise RuntimeError("Linux perf is not installed or not on PATH")
    with Path(output).open("w", encoding="utf-8") as handle:
        subprocess.run(
            ["perf", "script", "-i", str(data)],
            cwd=cwd,
            stdout=handle,
            check=True,
        )


__all__ = [
    "PerfCounter",
    "PerfStatResult",
    "perf_available",
    "perf_record",
    "perf_script",
    "perf_stat",
]
