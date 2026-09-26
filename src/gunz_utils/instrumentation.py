"""Dependency-free instrumentation primitives."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class Counter:
    value: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def add(self, amount: int = 1) -> int:
        with self._lock:
            self.value += amount
            return self.value


@dataclass(frozen=True)
class Timing:
    name: str
    seconds: float
    success: bool


class Timer:
    def __init__(self, name: str) -> None:
        self.name = name
        self.started = 0.0
        self.result: Timing | None = None

    def __enter__(self) -> Timer:
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.result = Timing(
            self.name,
            time.perf_counter() - self.started,
            exc is None,
        )


__all__ = ["Counter", "Timer", "Timing"]
