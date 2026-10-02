"""Deterministic micro-benchmark workloads for gunz-utils.

Executed by downstream performance-regression CI via gunz-bench.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gunz_bench import BenchmarkSpec

from gunz_utils.binary import ByteReader, encode_uvarint
from gunz_utils.io import atomic_write
from gunz_utils.iteration import batched
from gunz_utils.serialization import canonical_json


@dataclass(frozen=True)
class DownstreamWorkload:
    name: str
    func: Callable[[], object]
    repetitions: int
    warmup: int
    tags: tuple[str, ...]

    def to_spec(self) -> BenchmarkSpec:
        return BenchmarkSpec(
            name=self.name,
            func=self.func,
            repetitions=self.repetitions,
            warmup=self.warmup,
            tags=self.tags,
        )


def _workload_binary_varint() -> int:
    values = [0, 1, 127, 128, 16383, 16384, 2097151, 2097152, (1 << 63) - 1]
    total_len = 0
    for v in values * 500:
        encoded = encode_uvarint(v)
        reader = ByteReader(encoded)
        val = reader.read_uvarint()
        total_len += len(encoded) + val
    return total_len


def _workload_canonical_json() -> int:
    payload = {
        "metadata": {
            "run_id": "test_run_12345",
            "seed": 42,
            "tags": ["ci", "regression", "perf"],
        },
        "metrics": [
            {"name": f"metric_{i}", "value": float(i * 1.5), "unit": "ms"}
            for i in range(100)
        ],
    }
    encoded = canonical_json(payload)
    return len(encoded)


def _workload_iteration_batched() -> int:
    items = range(20000)
    batches = list(batched(items, 64))
    return len(batches)


def _workload_io_atomic_write() -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)
        for i in range(100):
            target = base / f"file_{i}.txt"
            atomic_write(target, f"content_{i}\n", mode="w", encoding="utf-8")
        return 100


WORKLOADS: tuple[DownstreamWorkload, ...] = (
    DownstreamWorkload(
        name="gunz_utils.binary.varint",
        func=_workload_binary_varint,
        repetitions=10,
        warmup=2,
        tags=("binary", "native", "accel"),
    ),
    DownstreamWorkload(
        name="gunz_utils.serialization.canonical_json",
        func=_workload_canonical_json,
        repetitions=10,
        warmup=2,
        tags=("serialization", "json", "accel"),
    ),
    DownstreamWorkload(
        name="gunz_utils.iteration.batched",
        func=_workload_iteration_batched,
        repetitions=10,
        warmup=2,
        tags=("iteration", "core"),
    ),
    DownstreamWorkload(
        name="gunz_utils.io.atomic_write",
        func=_workload_io_atomic_write,
        repetitions=5,
        warmup=1,
        tags=("io", "fs"),
    ),
)


def get_specs() -> list[BenchmarkSpec]:
    """Return all benchmark specifications for gunz-bench runner."""
    return [w.to_spec() for w in WORKLOADS]
