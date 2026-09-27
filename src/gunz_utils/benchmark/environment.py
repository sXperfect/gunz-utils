"""Host environment and benchmark-noise metadata."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NoiseInfo:
    load_1m: float | None
    load_5m: float | None
    load_15m: float | None
    affinity: tuple[int, ...] | None
    cpu_governors: tuple[str, ...]
    cgroup_memory_max: int | None


def capture_noise_info() -> NoiseInfo:
    """Capture inexpensive environment state relevant to benchmark noise."""
    try:
        load: tuple[float | None, float | None, float | None] = os.getloadavg()
    except (AttributeError, OSError):
        load = (None, None, None)
    affinity = (
        tuple(sorted(os.sched_getaffinity(0)))
        if hasattr(os, "sched_getaffinity")
        else None
    )
    governors: set[str] = set()
    cpu_root = Path("/sys/devices/system/cpu")
    for path in cpu_root.glob("cpu[0-9]*/cpufreq/scaling_governor"):
        try:
            governors.add(path.read_text().strip())
        except (OSError, PermissionError):
            pass
    memory_max = None
    try:
        raw = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if raw != "max":
            memory_max = int(raw)
    except (OSError, ValueError):
        pass
    return NoiseInfo(
        load_1m=load[0],
        load_5m=load[1],
        load_15m=load[2],
        affinity=affinity,
        cpu_governors=tuple(sorted(governors)),
        cgroup_memory_max=memory_max,
    )


__all__ = ["NoiseInfo", "capture_noise_info"]
