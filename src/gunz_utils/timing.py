"""Utilities for measuring elapsed wall-clock time."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import contextlib
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Literal

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = ["LapRecord", "Stopwatch", "Timer", "async_timer", "timer"]


@dataclass(frozen=True, slots=True)
class LapRecord:
    """One recorded split interval on a Timer."""

    index: int
    label: str | None
    split_seconds: float
    cumulative_seconds: float


class Timer:
    """Measure elapsed wall-clock time as a context manager or manually.

    Parameters
    ----------
    label : str or None, optional
        Descriptive label retained on the timer without automatic logging.
    auto_start : bool, optional
        Start timing immediately when ``True``. Defaults to ``True``.
    clock : Callable[[], float] or None, optional
        High-resolution clock callable, defaults to ``time.perf_counter``.
    """

    def __init__(self,
        label: str | None = None,
        *,
        auto_start: bool = True,
        clock: Callable[[], float] | None = None,
    ) -> None:
        """Initialize a timer, optionally starting it immediately."""
        if not isinstance(auto_start, bool):
            raise TypeError("auto_start must be a bool")
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self.label = label
        self._custom_clock = clock
        self._start_time: float | None = None
        self._end_time: float | None = None
        self._pause_start: float | None = None
        self._paused_duration: float = 0.0
        self._laps: list[LapRecord] = []
        if auto_start:
            self.start()

    def _now(self) -> float:
        return (
            self._custom_clock()
            if self._custom_clock is not None
            else time.perf_counter()
        )

    @property
    def is_running(self) -> bool:
        """Return True if timing has started and is not currently stopped or paused."""
        return (
            self._start_time is not None
            and self._end_time is None
            and self._pause_start is None
        )

    @property
    def is_paused(self) -> bool:
        """Return True if the timer is currently paused."""
        return self._pause_start is not None

    def start(self) -> None:
        """Start or restart the timer and clear any previous stop time.

        No parameters and no return value.
        """
        #? Monotonic high-resolution timing avoids wall-clock adjustments.
        self._start_time = self._now()
        self._end_time = None
        self._pause_start = None
        self._paused_duration = 0.0
        self._laps.clear()

    def pause(self) -> None:
        """Pause the timer, halting elapsed accumulation until resumed."""
        if (
            self._start_time is not None
            and self._end_time is None
            and self._pause_start is None
        ):
            self._pause_start = self._now()

    def resume(self) -> None:
        """Resume timing after a pause."""
        if self._pause_start is not None:
            self._paused_duration += self._now() - self._pause_start
            self._pause_start = None

    def stop(self) -> None:
        """Stop the timer, preserving the first stop time for idempotence.

        Stopping before start leaves elapsed at zero; a later start clears the
        stop timestamp, including implicit start on context entry.

        No parameters and no return value.
        """
        if self._end_time is None:
            if self._pause_start is not None:
                self._paused_duration += self._now() - self._pause_start
                self._pause_start = None
            self._end_time = self._now()

    def reset(self) -> None:
        """Reset the timer to an unstarted state."""
        self._start_time = None
        self._end_time = None
        self._pause_start = None
        self._paused_duration = 0.0
        self._laps.clear()

    @property
    def elapsed(self) -> float:
        """Return elapsed seconds, or ``0.0`` when timing has not started.

        Returns
        -------
        float
            The result of the operation.
        """
        if self._start_time is None:
            return 0.0
        if self._end_time is not None:
            end_time = self._end_time
        elif self._pause_start is not None:
            end_time = self._pause_start
        else:
            end_time = self._now()
        return max(0.0, end_time - self._start_time - self._paused_duration)

    @property
    def elapsed_ms(self) -> float:
        """Return elapsed duration in milliseconds."""
        return self.elapsed * 1000.0

    @property
    def elapsed_us(self) -> float:
        """Return elapsed duration in microseconds."""
        return self.elapsed * 1_000_000.0

    @property
    def elapsed_ns(self) -> int:
        """Return elapsed duration in integer nanoseconds."""
        return int(self.elapsed * 1_000_000_000)

    @property
    def laps(self) -> tuple[LapRecord, ...]:
        """Return all recorded lap records."""
        return tuple(self._laps)

    def lap(self,
        label: str | None = None,
    ) -> float:
        """Record a split lap interval and return the lap duration in seconds."""
        if self._start_time is None:
            self.start()
        current_cumulative = self.elapsed
        previous_cumulative = (
            self._laps[-1].cumulative_seconds if self._laps else 0.0
        )
        split = max(0.0, current_cumulative - previous_cumulative)
        rec = LapRecord(
            index=len(self._laps) + 1,
            label=label,
            split_seconds=split,
            cumulative_seconds=current_cumulative,
        )
        self._laps.append(rec)
        return split

    def __enter__(self) -> Timer:
        """Enter the context, starting the timer if it was not started."""
        if self._start_time is None:
            self.start()
        return self

    def __exit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> Literal[False]:
        """Stop timing on context exit without suppressing exceptions."""
        self.stop()
        return False

    async def __aenter__(self) -> Timer:
        """Enter async context, starting the timer if unstarted."""
        return self.__enter__()

    async def __aexit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> Literal[False]:
        """Stop timing on async context exit."""
        return self.__exit__(exc_type, exc_value, traceback)


class Stopwatch:
    """Accumulate elapsed duration across multiple start/stop intervals."""

    def __init__(self,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if clock is not None and not callable(clock):
            raise TypeError("clock must be callable")
        self._custom_clock = clock
        self._intervals: list[float] = []
        self._current_start: float | None = None

    def _now(self) -> float:
        return (
            self._custom_clock()
            if self._custom_clock is not None
            else time.perf_counter()
        )

    def start(self) -> None:
        """Start or resume timing an interval."""
        if self._current_start is None:
            self._current_start = self._now()

    def stop(self) -> float:
        """Stop the current interval and return its duration."""
        if self._current_start is not None:
            interval = max(0.0, self._now() - self._current_start)
            self._intervals.append(interval)
            self._current_start = None
            return interval
        return 0.0

    def reset(self) -> None:
        """Reset the stopwatch, clearing all intervals."""
        self._intervals.clear()
        self._current_start = None

    @property
    def is_running(self) -> bool:
        """Return True if an interval is currently being timed."""
        return self._current_start is not None

    @property
    def total_elapsed(self) -> float:
        """Return total elapsed time across all completed and current intervals."""
        current = (
            max(0.0, self._now() - self._current_start)
            if self._current_start is not None
            else 0.0
        )
        return sum(self._intervals) + current

    @property
    def count(self) -> int:
        """Return total number of recorded and in-progress intervals."""
        return len(self._intervals) + (1 if self._current_start is not None else 0)

    @property
    def mean_elapsed(self) -> float:
        """Return average interval duration, or 0.0 if no intervals exist."""
        c = self.count
        return self.total_elapsed / c if c > 0 else 0.0

    def __enter__(self) -> Stopwatch:
        self.start()
        return self

    def __exit__(self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> Literal[False]:
        self.stop()
        return False


@contextlib.asynccontextmanager
async def async_timer(
    label: str | None = None,
    *,
    clock: Callable[[], float] | None = None,
) -> AsyncIterator[Timer]:
    """Yield a started Timer in an async context."""
    timed = Timer(label, clock=clock)
    try:
        yield timed
    finally:
        timed.stop()


@contextlib.contextmanager
def timer(
    label: str | None = None,
    *,
    clock: Callable[[], float] | None = None,
) -> Iterator[Timer]:
    """Yield a started :class:`Timer` and stop it when the context exits.

    Parameters
    ----------
    label : str or None, optional
        Descriptive label retained on the yielded timer.
    clock : Callable[[], float] or None, optional
        Clock callable to use for measurement, by default time.perf_counter.

    Yields
    ------
    Timer
        A started timer whose elapsed value is fixed after context exit.
    """
    timed = Timer(label, clock=clock)
    try:
        yield timed
    finally:
        timed.stop()
