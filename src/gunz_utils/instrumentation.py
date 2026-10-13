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
        """add() function.

        Parameters
        ----------
        amount : int
            amount parameter.

        Returns
        -------
        int
            The result of the operation.

        Raises
        ------
        ValueError
            If amount is not an integer (including bool).
        """
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValueError(f"amount must be an integer, got {amount!r}")
        with self._lock:
            self.value += amount
            return self.value


@dataclass(frozen=True)
class Timing:
    name: str
    seconds: float
    success: bool


class Timer:
    def __init__(self,
        name: str,
    ) -> None:
        self.name = name
        self.started = 0.0
        self._active = False
        self.result: Timing | None = None

    def __enter__(self) -> Timer:
        if self._active:
            #? The Timer is not reentrant: a nested __enter__ on the same
            #? object would overwrite `started` and silently corrupt the outer
            #? block's elapsed, so fail loudly instead of returning a wrong
            #? measurement. Sequential reuse (enter/exit/enter/exit) is fine.
            raise RuntimeError(
                f"Timer {self.name!r} is not reentrant; nested re-entry would "
                "corrupt the outer measurement"
            )
        self._active = True
        self.started = time.perf_counter()
        return self

    def __exit__(self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        if not self._active:
            #? Symmetric guard to __enter__: an __exit__ without a matching
            #? __enter__ (or a second __exit__ after a normal one) would
            #? silently record a bogus elapsed based on started=0.0 or the
            #? previous entry's start. Fail loudly instead.
            raise RuntimeError(
                f"Timer {self.name!r} is not active; __exit__ requires a "
                "matching __enter__"
            )
        self.result = Timing(
            self.name,
            time.perf_counter() - self.started,
            exc is None,
        )
        self._active = False


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
        if not isinstance(name, str):
            raise TypeError(f"name must be a str, got {type(name).__name__}")
        try:
            metadata_snapshot = copy.deepcopy(metadata)
        except Exception:
            #? Instrumentation must not break the instrumented operation when a
            #? metadata value cannot be deep-copied. Fall back to the original
            #? dict so the body still runs and a span is still recorded.
            metadata_snapshot = metadata
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
            If n is negative or not an integer.
        """
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError(f"n must be a non-negative integer, got {n!r}")
        with self._lock:
            snapshot = list(self.events)
        return sorted(
            snapshot,
            key=lambda event: event.duration,
            reverse=True,
        )[:n]
