"""Tests for reversible signal-handler registration."""

from __future__ import annotations

import signal
from unittest.mock import patch

import pytest

from gunz_utils.signals import (
    install_async_signal_handlers,
    install_termination_handler,
)


def test_termination_handler_invokes_callback_and_restores_previous() -> None:
    previous = signal.getsignal(signal.SIGTERM)
    received: list[int] = []

    registration = install_termination_handler(
        received.append,
        exit_after=False,
    )
    try:
        registration.handler(signal.SIGTERM, None)
        assert received == [signal.SIGTERM]
        assert signal.getsignal(signal.SIGTERM) is registration.handler
    finally:
        registration.restore()

    assert signal.getsignal(signal.SIGTERM) == previous


def test_termination_handler_default_raises_shell_compatible_exit() -> None:
    received: list[int] = []

    registration = install_termination_handler(
        received.append,
    )
    try:
        with pytest.raises(SystemExit) as exc_info:
            registration.handler(signal.SIGTERM, None)
    finally:
        registration.restore()

    assert received == [signal.SIGTERM]
    assert exc_info.value.code == 128 + signal.SIGTERM


def test_signal_registration_restore_is_idempotent() -> None:
    previous = signal.getsignal(signal.SIGTERM)
    registration = install_termination_handler(
        lambda _signum: None,
        exit_after=False,
    )

    registration.restore()
    registration.restore()

    assert signal.getsignal(signal.SIGTERM) == previous


def test_termination_handler_rejects_non_callable_callback() -> None:
    invalid = object()

    with pytest.raises(TypeError, match="callable"):
        install_termination_handler(invalid)



class _FakeLoop:
    def __init__(
        self,
        *,
        fail_on: int | None = None,
    ) -> None:
        self.fail_on = fail_on
        self.added: list[
            tuple[int, object, tuple[object, ...]]
        ] = []
        self.removed: list[int] = []

    def add_signal_handler(
        self,
        signum: int,
        callback: object,
        *args: object,
    ) -> None:
        if signum == self.fail_on:
            raise NotImplementedError("unsupported")
        self.added.append(
            (
                signum,
                callback,
                args,
            )
        )

    def remove_signal_handler(
        self,
        signum: int,
    ) -> bool:
        self.removed.append(signum)
        return True


def test_async_signal_registration_deduplicates_and_restores() -> None:
    loop = _FakeLoop()
    received: list[int] = []

    with (
        patch(
            "gunz_utils.signals.signal.getsignal",
            side_effect=lambda signum: f"previous-{signum}",
        ),
        patch("gunz_utils.signals.signal.signal") as restore,
    ):
        registration = install_async_signal_handlers(
            received.append,
            signums=(
                signal.SIGTERM,
                signal.SIGINT,
                signal.SIGTERM,
            ),
            loop=loop,
        )

        assert registration.signums == (
            signal.SIGTERM,
            signal.SIGINT,
        )
        first = loop.added[0]
        callback = first[1]
        assert callable(callback)
        callback(*first[2])
        assert received == [signal.SIGTERM]

        registration.restore()
        registration.restore()

    assert loop.removed == [
        signal.SIGINT,
        signal.SIGTERM,
    ]
    assert restore.call_count == 2


def test_async_signal_registration_rolls_back_partial_failure() -> None:
    loop = _FakeLoop(
        fail_on=signal.SIGTERM,
    )

    with (
        patch(
            "gunz_utils.signals.signal.getsignal",
            side_effect=lambda signum: f"previous-{signum}",
        ),
        patch("gunz_utils.signals.signal.signal") as restore,
    ):
        with pytest.raises(NotImplementedError, match="unsupported"):
            install_async_signal_handlers(
                lambda _signum: None,
                signums=(
                    signal.SIGINT,
                    signal.SIGTERM,
                ),
                loop=loop,
            )

    assert loop.removed == [signal.SIGINT]
    assert restore.call_count == 2


def test_async_signal_registration_validates_signal_list() -> None:
    loop = _FakeLoop()

    with pytest.raises(ValueError, match="must not be empty"):
        install_async_signal_handlers(
            lambda _signum: None,
            signums=(),
            loop=loop,
        )

    with pytest.raises(ValueError, match="positive integer"):
        install_async_signal_handlers(
            lambda _signum: None,
            signums=(True,),
            loop=loop,
        )
