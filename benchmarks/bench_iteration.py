"""Microbenchmarks for iteration batching helpers."""

from __future__ import annotations

import timeit

from gunz_utils.iteration import batched, chunked


def benchmark(size: int = 1_000_000, batch_size: int = 64) -> dict[str, float]:
    data = list(range(size))
    return {
        "chunked_seconds": min(
            timeit.repeat(lambda: list(chunked(data, batch_size)), number=1, repeat=5)
        ),
        "batched_seconds": min(
            timeit.repeat(lambda: list(batched(data, batch_size)), number=1, repeat=5)
        ),
    }


if __name__ == "__main__":
    for name, seconds in benchmark().items():
        print(f"{name}: {seconds:.6f}")
