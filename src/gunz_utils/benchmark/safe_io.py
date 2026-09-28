"""Safe benchmark-result JSON persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .result import BenchmarkResult, BenchmarkStats, SystemInfo

DEFAULT_MAX_RESULT_BYTES = 16 * 1024 * 1024


def load_result_checked(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
) -> BenchmarkResult:
    """Load a benchmark result with size and structural validation."""
    item = Path(path)
    if (
        isinstance(max_bytes, bool)
        or not isinstance(max_bytes, int)
        or max_bytes < 1
    ):
        raise ValueError("max_bytes must be a positive integer")
    with item.open("rb") as handle:
        payload = handle.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("benchmark result exceeds size limit")
    data: Any = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("benchmark result must be a JSON object")
    required = {
        "name",
        "samples",
        "stats",
        "warmup",
        "iterations",
        "system",
        "schema_version",
    }
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


__all__ = ["DEFAULT_MAX_RESULT_BYTES", "load_result_checked"]
