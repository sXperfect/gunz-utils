"""Utilities for measuring elapsed wall-clock time."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import contextlib
import time
from collections.abc import Callable, Iterator
from typing import Literal

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = ["Timer", "timer"]


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
        if auto_start:
            self.start()

    def _now(self) -> float:
        return (
            self._custom_clock()
            if self._custom_clock is not None
            else time.perf_counter()
        )

    def start(self) -> None:
        """Start or restart the timer and clear any previous stop time.

        No parameters and no return value.
        """
        #? Monotonic high-resolution timing avoids wall-clock adjustments.
        self._start_time = self._now()
        self._end_time = None

    def stop(self) -> None:
        """Stop the timer, preserving the first stop time for idempotence.

        Stopping before start leaves elapsed at zero; a later start clears the
        stop timestamp, including implicit start on context entry.

        No parameters and no return value.
        """
        if self._end_time is None:
            self._end_time = self._now()

    def reset(self) -> None:
        """Reset the timer to an unstarted state."""
        self._start_time = None
        self._end_time = None

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
        end_time = (
            self._end_time if self._end_time is not None else self._now()
        )
        return end_time - self._start_time

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
