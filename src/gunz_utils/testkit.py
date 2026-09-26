"""Additional deterministic testing helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from collections.abc import Iterator


@dataclass
class ManualClock:
    now: float = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("cannot move clock backwards")
        self.now += seconds


def fuzz_integers(*, seed: int, count: int, minimum: int = 0, maximum: int = 2**31 - 1) -> Iterator[int]:
    """Yield deterministic pseudo-random integers for lightweight fuzz tests."""
    if count < 0:
        raise ValueError("count must be non-negative")
    rng = random.Random(seed)
    for _ in range(count):
        yield rng.randint(minimum, maximum)


__all__ = ["ManualClock", "fuzz_integers"]
