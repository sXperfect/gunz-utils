"""Dependency-free instrumentation primitives."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import copy
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class Counter:
    value: int = 0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def add(self,
        amount: int = 1,
    ) -> int:
        """Add to the counter atomically.

        Parameters
        ----------
        amount : int, default=1
            Amount to add. Must be a non-negative integer.

        Returns
        -------
        int
            The updated counter value.
        """
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("amount must be a non-negative integer")
        with self._lock:
            self.value += amount
            return self.value

    def reset(self) -> int:
        """Reset the counter to zero and return the previous value.

        Returns
        -------
        int
            The counter value prior to reset.
        """
        with self._lock:
            prev = self.value
            self.value = 0
            return prev


@dataclass(frozen=True)
class Timing:
    name: str
    seconds: float
    success: bool


class Timer:
    def __init__(self,
        name: str,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        self.name = name
        self.started = 0.0
        self.result: Timing | None = None

    def reset(self) -> None:
        """Reset timer state and cleared recorded results."""
        self.started = 0.0
        self.result = None

    def __enter__(self) -> Timer:
        self.started = time.perf_counter()
        return self

    def __exit__(self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        self.result = Timing(
            self.name,
            time.perf_counter() - self.started,
            exc is None,
        )

    @property
    def elapsed(self) -> float:
        """Return elapsed duration in seconds."""
        if self.result is not None:
            return self.result.seconds
        if self.started > 0.0:
            return time.perf_counter() - self.started
        return 0.0


__all__ = ["Counter", "Timer", "Timing", "Trace", "TraceEvent"]



@dataclass(frozen=True)
class TraceEvent:
    """One completed execution span.

    Parameters
    ----------
    name : str
        Span name.
    start : float
        Monotonic perf-counter value at span entry.
    duration : float
        Elapsed seconds.
    metadata : dict[str, Any]
        Caller-supplied metadata copied at span creation.
    success : bool
        Whether the span exited without an exception.
    """

    name: str
    start: float
    duration: float
    metadata: dict[str, Any]
    success: bool


@dataclass
class Trace:
    """Collect lightweight in-process execution spans.

    The recorder is dependency-free and intentionally does not emit logs or
    export telemetry. Callers decide how to persist, aggregate, or visualize
    the recorded spans.
    """

    events: list[TraceEvent] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock, repr=False)

    @contextmanager
    def span(self,
        name: str,
        **metadata: Any,
    ) -> Iterator[None]:
        """Record elapsed time and success for one execution span.

        Parameters
        ----------
        name : str
            Human-readable span name.
        **metadata : Any
            Metadata copied into the completed event.

        Yields
        ------
        None
            Control to the instrumented operation.

        Notes
        -----
        Exceptions are never suppressed. Failed spans are still recorded with
        success set to False.
        """
        metadata_snapshot = copy.deepcopy(metadata)
        start = time.perf_counter()
        success = False
        try:
            yield
            success = True
        finally:
            event = TraceEvent(
                name=name,
                start=start,
                duration=time.perf_counter() - start,
                metadata=metadata_snapshot,
                success=success,
            )
            with self._lock:
                self.events.append(event)

    def slowest(self,
        n: int = 10,
    ) -> list[TraceEvent]:
        """Return up to n slowest completed spans.

        Parameters
        ----------
        n : int, optional
            Maximum events to return. Must be non-negative.

        Returns
        -------
        list[TraceEvent]
            Events sorted by descending duration.

        Raises
        ------
        ValueError
            If n is negative.
        """
        if n < 0:
            raise ValueError("n must be non-negative")
        with self._lock:
            snapshot = list(self.events)
        return sorted(
            snapshot,
            key=lambda event: event.duration,
            reverse=True,
        )[:n]
