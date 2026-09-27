"""Reversible process and asyncio signal-handler utilities."""

from __future__ import annotations

import asyncio
import signal
from collections.abc import Callable
from dataclasses import dataclass
from types import FrameType
from typing import Any, Literal

SignalCallback = Callable[[int], None]


@dataclass
class SignalRegistration:
    """Installed process signal handler with idempotent restoration."""

    signum: int
    previous: Any
    handler: Callable[[int, FrameType | None], None]
    _restored: bool = False

    def restore(self) -> None:
        """Restore the handler that was active before registration."""
        if self._restored:
            return
        signal.signal(
            self.signum,
            self.previous,
        )
        self._restored = True

    def __enter__(self) -> SignalRegistration:
        """Return the active registration."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> Literal[False]:
        """Restore the previous handler without suppressing exceptions."""
        self.restore()
        return False


@dataclass
class AsyncSignalRegistration:
    """Asyncio loop signal handlers with idempotent restoration."""

    loop: asyncio.AbstractEventLoop
    signums: tuple[int, ...]
    previous: dict[int, Any]
    _restored: bool = False

    def restore(self) -> None:
        """Remove loop handlers and restore previous process handlers."""
        if self._restored:
            return
        for signum in reversed(self.signums):
            try:
                self.loop.remove_signal_handler(signum)
            except (NotImplementedError, RuntimeError):
                pass
            signal.signal(
                signum,
                self.previous[signum],
            )
        self._restored = True

    def __enter__(self) -> AsyncSignalRegistration:
        """Return the active registration."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> Literal[False]:
        """Restore all previous handlers without suppressing exceptions."""
        self.restore()
        return False


def install_async_signal_handlers(
    callback: SignalCallback,
    *,
    signums: tuple[int, ...] = (
        signal.SIGINT,
        signal.SIGTERM,
    ),
    loop: asyncio.AbstractEventLoop | None = None,
) -> AsyncSignalRegistration:
    """Register synchronous callbacks on an asyncio event loop.

    Parameters
    ----------
    callback : SignalCallback
        Synchronous callback receiving the signal number.
    signums : tuple[int, ...], optional
        Signals to register. Duplicates are removed while preserving order.
    loop : asyncio.AbstractEventLoop | None, optional
        Event loop to modify. Defaults to asyncio.get_running_loop().

    Returns
    -------
    AsyncSignalRegistration
        Registration object that restores pre-existing process handlers.

    Raises
    ------
    TypeError
        If callback is not callable.
    ValueError
        If no signals are supplied or a signal number is invalid.
    NotImplementedError
        If the loop/platform does not support add_signal_handler.

    Notes
    -----
    The callback itself must be synchronous; it can set an asyncio.Event or
    schedule async work. Registration and restoration must run in the main
    thread on platforms where Python signal handling requires it.
    """
    if not callable(callback):
        raise TypeError("callback must be callable")

    unique: list[int] = []
    seen: set[int] = set()
    for signum in signums:
        if (
            isinstance(signum, bool)
            or not isinstance(signum, int)
            or signum <= 0
        ):
            raise ValueError(
                "signums must contain positive integer signal numbers"
            )
        if signum not in seen:
            seen.add(signum)
            unique.append(signum)

    if not unique:
        raise ValueError("signums must not be empty")

    event_loop = loop or asyncio.get_running_loop()
    previous: dict[int, Any] = {}
    registered: list[int] = []

    try:
        for signum in unique:
            previous[signum] = signal.getsignal(signum)
            event_loop.add_signal_handler(
                signum,
                callback,
                signum,
            )
            registered.append(signum)
    except BaseException:
        for signum in reversed(tuple(previous)):
            if signum in registered:
                try:
                    event_loop.remove_signal_handler(signum)
                except (NotImplementedError, RuntimeError):
                    pass
            signal.signal(
                signum,
                previous[signum],
            )
        raise

    return AsyncSignalRegistration(
        loop=event_loop,
        signums=tuple(unique),
        previous=previous,
    )


def install_termination_handler(
    callback: SignalCallback,
    *,
    signum: int = signal.SIGTERM,
    exit_after: bool = True,
) -> SignalRegistration:
    """Install a callback for termination/preemption signals.

    Parameters
    ----------
    callback : SignalCallback
        Called with the received signal number.
    signum : int, optional
        Signal to register. Defaults to SIGTERM.
    exit_after : bool, optional
        Raise SystemExit with shell-compatible code 128 + signum after the
        callback completes. Defaults to True.

    Returns
    -------
    SignalRegistration
        Registration object that can restore the previous handler.

    Notes
    -----
    Python only permits signal registration from the main thread. The native
    ValueError from signal.signal is intentionally allowed to propagate.
    """
    if not callable(callback):
        raise TypeError("callback must be callable")

    previous = signal.getsignal(signum)

    def handler(
        received: int,
        _frame: FrameType | None,
    ) -> None:
        callback(received)
        if exit_after:
            raise SystemExit(128 + received)

    signal.signal(
        signum,
        handler,
    )
    return SignalRegistration(
        signum=signum,
        previous=previous,
        handler=handler,
    )


__all__ = [
    "AsyncSignalRegistration",
    "SignalCallback",
    "SignalRegistration",
    "install_async_signal_handlers",
    "install_termination_handler",
]
