"""Additional deterministic testing helpers."""

from __future__ import annotations

import math
import random
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class ManualClock:
    now: float = 0.0

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(float(seconds))
            or seconds < 0
        ):
            raise ValueError(
                "clock advance must be a finite non-negative number"
            )
        candidate = self.now + float(seconds)
        if not math.isfinite(candidate):
            raise OverflowError("manual clock exceeds finite float range")
        self.now = candidate


def fuzz_integers(
    *, seed: int, count: int, minimum: int = 0, maximum: int = 2**31 - 1
) -> Iterator[int]:
    """Yield deterministic pseudo-random integers for lightweight fuzz tests."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")
    for name, value in (("minimum", minimum), ("maximum", maximum)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer")
    if minimum > maximum:
        raise ValueError("minimum must be <= maximum")
    rng = random.Random(seed)
    for _ in range(count):
        yield rng.randint(minimum, maximum)


__all__ = ["ManualClock", "fuzz_integers"]
