"""Safe benchmark-result JSON persistence."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .result import BenchmarkResult, BenchmarkStats, SystemInfo

DEFAULT_MAX_RESULT_BYTES = 16 * 1024 * 1024


def _non_negative_int(value: object, *, name: str, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    minimum = 1 if positive else 0
    if value < minimum:
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{name} must be {qualifier}")
    return value


def _finite_non_negative(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return result


def load_result_checked(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_RESULT_BYTES,
) -> BenchmarkResult:
    """Load a benchmark result with bounded reads and structural validation."""
    max_bytes = _non_negative_int(max_bytes, name="max_bytes", positive=True)

    item = Path(path)
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

    if not isinstance(data["name"], str) or not data["name"]:
        raise ValueError("benchmark name must be a non-empty string")
    if not isinstance(data["samples"], list) or not data["samples"]:
        raise ValueError("benchmark samples must be a non-empty array")
    samples = tuple(
        _finite_non_negative(value, name="benchmark sample")
        for value in data["samples"]
    )

    warmup = _non_negative_int(data["warmup"], name="warmup")
    iterations = _non_negative_int(
        data["iterations"],
        name="iterations",
        positive=True,
    )
    if iterations != len(samples):
        raise ValueError("benchmark iteration count does not match samples")

    schema_version = _non_negative_int(
        data["schema_version"],
        name="schema_version",
        positive=True,
    )
    if schema_version != 1:
        raise ValueError(f"unsupported benchmark schema version: {schema_version}")

    stats_data = data["stats"]
    if not isinstance(stats_data, dict):
        raise ValueError("benchmark stats must be an object")
    stat_names = (
        "minimum",
        "median",
        "mean",
        "p95",
        "p99",
        "maximum",
        "stddev",
    )
    normalized_stats = {
        name: _finite_non_negative(stats_data.get(name), name=f"stats.{name}")
        for name in stat_names
    }
    ops_value = stats_data.get("ops_per_second")
    if isinstance(ops_value, bool) or not isinstance(ops_value, (int, float)):
        raise ValueError("stats.ops_per_second must be numeric")
    ops_per_second = float(ops_value)
    if math.isnan(ops_per_second) or ops_per_second < 0:
        raise ValueError("stats.ops_per_second must be non-negative and not NaN")
    stats = BenchmarkStats(
        **normalized_stats,
        ops_per_second=ops_per_second,
    )

    system_data = data["system"]
    if not isinstance(system_data, dict):
        raise ValueError("benchmark system must be an object")
    required_system = {"python", "platform", "machine", "processor", "cpu_count"}
    if required_system - system_data.keys():
        raise ValueError("benchmark system is missing required fields")
    if any(
        not isinstance(system_data[name], str)
        for name in ("python", "platform", "machine", "processor")
    ):
        raise ValueError("benchmark system text fields must be strings")
    cpu_count = system_data["cpu_count"]
    if cpu_count is not None and (
        isinstance(cpu_count, bool)
        or not isinstance(cpu_count, int)
        or cpu_count < 1
    ):
        raise ValueError("system.cpu_count must be a positive integer or None")
    system = SystemInfo(
        python=system_data["python"],
        platform=system_data["platform"],
        machine=system_data["machine"],
        processor=system_data["processor"],
        cpu_count=cpu_count,
    )

    parameters = data.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("benchmark parameters must be an object")

    return BenchmarkResult(
        name=data["name"],
        samples=samples,
        stats=stats,
        warmup=warmup,
        iterations=iterations,
        system=system,
        parameters=dict(parameters),
        schema_version=schema_version,
    )


__all__ = ["DEFAULT_MAX_RESULT_BYTES", "load_result_checked"]
