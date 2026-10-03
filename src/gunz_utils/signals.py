"""Reversible process and asyncio signal-handler utilities."""

from __future__ import annotations

import asyncio
import inspect
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
    if isinstance(signum, bool) or not isinstance(signum, int) or signum <= 0:
        raise ValueError("signum must be a positive integer")
    if not isinstance(exit_after, bool):
        raise ValueError("exit_after must be bool")

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


class GracefulShutdown:
    """Coordinated async graceful shutdown on OS termination signals or cancellation.

    Parameters
    ----------
    signums : tuple[int, ...], optional
        Signals to capture. Defaults to (SIGINT, SIGTERM).
    timeout : float, optional
        Maximum timeout in seconds to wait for async cleanup callbacks.
    loop : asyncio.AbstractEventLoop | None, optional
        Target event loop.
    """

    def __init__(
        self,
        *,
        signums: tuple[int, ...] = (signal.SIGINT, signal.SIGTERM),
        timeout: float = 10.0,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive number")
        self.signums = signums
        self.timeout = float(timeout)
        self._loop = loop
        self._callbacks: list[Callable[[], Any]] = []
        self._shutdown_event: asyncio.Event | None = None
        self._registration: AsyncSignalRegistration | None = None
        self._signal_received: int | None = None

    @property
    def is_shutting_down(self) -> bool:
        """Whether shutdown has been triggered."""
        return self._shutdown_event is not None and self._shutdown_event.is_set()

    @property
    def signal_received(self) -> int | None:
        """Return the signal number that triggered shutdown, if any."""
        return self._signal_received

    def _get_event(self) -> asyncio.Event:
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        return self._shutdown_event

    def add_callback(self, callback: Callable[[], Any]) -> None:
        """Register a sync or async cleanup callback invoked on shutdown."""
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._callbacks.append(callback)

    def trigger_shutdown(self, signum: int | None = None) -> None:
        """Programmatically trigger shutdown."""
        self._signal_received = signum
        self._get_event().set()

    async def wait_for_shutdown(self) -> int | None:
        """Wait until a shutdown signal is received or triggered."""
        await self._get_event().wait()
        return self._signal_received

    async def run_cleanup(self) -> list[tuple[Callable[[], Any], BaseException]]:
        """Run all registered callbacks in LIFO order within the timeout."""
        errors: list[tuple[Callable[[], Any], BaseException]] = []
        for cb in reversed(self._callbacks):
            try:
                res = cb()
                if inspect.isawaitable(res):
                    await asyncio.wait_for(res, timeout=self.timeout)
            except BaseException as exc:
                errors.append((cb, exc))
        return errors

    async def __aenter__(self) -> GracefulShutdown:
        self._get_event()
        loop = self._loop or asyncio.get_running_loop()
        try:
            self._registration = install_async_signal_handlers(
                self.trigger_shutdown,
                signums=self.signums,
                loop=loop,
            )
        except (NotImplementedError, ValueError):
            self._registration = None
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> bool:
        if self._registration is not None:
            self._registration.restore()
            self._registration = None
        is_cancelled = (
            exc_type is not None and issubclass(exc_type, asyncio.CancelledError)
        )
        if self.is_shutting_down or is_cancelled:
            if not self.is_shutting_down:
                self.trigger_shutdown()
            cleanup_task = asyncio.create_task(self.run_cleanup())
            while not cleanup_task.done():
                try:
                    await asyncio.shield(cleanup_task)
                except asyncio.CancelledError:
                    pass
        return False


__all__ = [
    "AsyncSignalRegistration",
    "GracefulShutdown",
    "SignalCallback",
    "SignalRegistration",
    "install_async_signal_handlers",
    "install_termination_handler",
]
