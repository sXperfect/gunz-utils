"""Utilities for measuring elapsed wall-clock time."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import contextlib
import time

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "BSD 3-Clause"
__version__ = "1.6.0"

__all__ = ["Timer", "timer"]


class Timer:
    """Measure elapsed wall-clock time as a context manager or manually.

    Parameters
    ----------
    label : str or None, optional
        Descriptive label retained on the timer without automatic logging.
    auto_start : bool, optional
        Start timing immediately when ``True``. Defaults to ``True``.
    """

    def __init__(
        self,
        label: str | None = None,
        *,
        auto_start: bool = True,
    ) -> None:
        """Initialize a timer, optionally starting it immediately."""
        self.label = label
        self._start_time: float | None = None
        self._end_time: float | None = None
        if auto_start:
            self.start()

    def start(self) -> None:
        """Start or restart the timer and clear any previous stop time."""
        #? Monotonic high-resolution timing avoids wall-clock adjustments.
        self._start_time = time.perf_counter()
        self._end_time = None

    def stop(self) -> None:
        """Stop the timer, preserving the first stop time for idempotence."""
        if self._end_time is None:
            self._end_time = time.perf_counter()

    @property
    def elapsed(self) -> float:
        """Return elapsed seconds, or ``0.0`` when timing has not started."""
        if self._start_time is None:
            return 0.0
        end_time = (
            self._end_time if self._end_time is not None else time.perf_counter()
        )
        return end_time - self._start_time

    def __enter__(self) -> Timer:
        """Enter the context, starting the timer if it was not started."""
        if self._start_time is None:
            self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> bool:
        """Stop timing on context exit without suppressing exceptions."""
        self.stop()
        return False


@contextlib.contextmanager
def timer(label: str | None = None):
    """Yield a started :class:`Timer` and stop it when the context exits.

    Parameters
    ----------
    label : str or None, optional
        Descriptive label retained on the yielded timer.

    Yields
    ------
    Timer
        A started timer whose elapsed value is fixed after context exit.
    """
    timed = Timer(label)
    try:
        yield timed
    finally:
        timed.stop()
