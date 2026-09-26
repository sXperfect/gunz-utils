"""Safe benchmark-result JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .result import BenchmarkResult, BenchmarkStats, SystemInfo


def load_result_checked(
    path: str | Path,
    *,
    max_bytes: int = 16 * 1024 * 1024,
) -> BenchmarkResult:
    """Load a benchmark result with size and structural validation."""
    item = Path(path)
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if item.stat().st_size > max_bytes:
        raise ValueError("benchmark result exceeds size limit")
    data: Any = json.loads(item.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("benchmark result must be a JSON object")
    required = {"name", "samples", "stats", "warmup", "iterations", "system", "schema_version"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"benchmark result missing fields: {sorted(missing)}")
    if not isinstance(data["samples"], list):
        raise ValueError("benchmark samples must be an array")
    if data["iterations"] != len(data["samples"]):
        raise ValueError("benchmark iteration count does not match samples")
    stats = BenchmarkStats(**data["stats"])
    system = SystemInfo(**data["system"])
    return BenchmarkResult(
        name=data["name"],
        samples=tuple(float(value) for value in data["samples"]),
        stats=stats,
        warmup=int(data["warmup"]),
        iterations=int(data["iterations"]),
        system=system,
        parameters=data.get("parameters", {}),
        schema_version=int(data["schema_version"]),
    )


__all__ = ["load_result_checked"]
