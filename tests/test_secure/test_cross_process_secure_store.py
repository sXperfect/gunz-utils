"""Acknowledged independent-process SecureStore flock and transaction proofs."""

from __future__ import annotations

import multiprocessing
import os
import sqlite3
import time
from collections.abc import Callable
from contextlib import ExitStack, closing
from functools import partial
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from gunz_utils.ext import secure_store
from gunz_utils.ext.secure_store import SecureStore

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="real POSIX flock contention proof"
)

_WAIT = 15.0
Command = tuple[str, str, str]
Message = tuple[str, str | int]


def _command(channel: Connection) -> Command:
    if not channel.poll(_WAIT):
        raise TimeoutError("parent command acknowledgment deadline")
    return cast(Command, channel.recv())


def _paused_audit(
    channel: Connection,
    original: Callable[[str, str, str | None, bool], None],
    caller: str,
    action: str,
    secret_name: str | None,
    allowed: bool,
) -> None:
    channel.send(("held", "transaction-holder"))
    if _command(channel)[0] != "release":
        raise RuntimeError("parent aborted the bounded proof")
    original(caller, action, secret_name, allowed)


def _paused_publication(
    channel: Connection,
    store: SecureStore,
    original: Callable[..., None],
    *,
    passphrase_mode: bool,
) -> None:
    channel.send(("rotated-holding", store._key_generation))
    if _command(channel)[0] != "release":
        raise RuntimeError("parent aborted the bounded proof")
    original(passphrase_mode=passphrase_mode)


def _store_process(channel: Connection, base: str, passphrase: str | None) -> None:
    """Own a fresh store/SQLite connection and acknowledge actual flock contention."""
    import fcntl

    operation = "startup"
    original_lock = secure_store._lock_fd

    def observed_lock(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            channel.send(("contended", operation))
        original_lock(fd)
        channel.send(("acquired", operation))

    secure_store._lock_fd = observed_lock
    try:
        with SecureStore(base_dir=base) as store:
            channel.send(("ready", os.getpid()))
            while True:
                operation, name, value = _command(channel)
                if operation == "stop":
                    return
                try:
                    if operation == "unlock":
                        store.unlock(passphrase)
                    elif operation == "set":
                        store.set(name, value, caller=name)
                    elif operation == "get":
                        store.get(name)
                    elif operation == "rotate":
                        store.rotate_master_key(passphrase)
                    elif operation == "first-unlock-holder":
                        with store._coordination_lock:
                            channel.send(("held", operation))
                            if _command(channel)[0] != "release":
                                return
                            store.unlock(passphrase)
                            store.set("first", "first-value", caller="first")
                    elif operation == "transaction-holder":
                        with patch.object(
                            store,
                            "_audit",
                            partial(_paused_audit, channel, store._audit),
                        ):
                            store.set("held", "held-value", caller="held")
                    elif operation == "rotation-holder":
                        with patch.object(
                            store,
                            "_promote_pending_key_material",
                            partial(
                                _paused_publication,
                                channel,
                                store,
                                store._promote_pending_key_material,
                            ),
                        ):
                            store.rotate_master_key(passphrase)
                    elif operation == "lock-holder":
                        with store._coordination_lock:
                            channel.send(("held", operation))
                            if _command(channel)[0] != "release":
                                return
                    else:
                        raise ValueError("unknown synthetic worker operation")
                except RuntimeError as error:
                    if "stale" not in str(error):
                        raise
                    channel.send(("stale", operation))
                else:
                    channel.send(("done", store._key_generation))
    except BaseException as error:
        channel.send(("error", f"{type(error).__name__}: {error}"))
    finally:
        channel.close()


class _Worker:
    def __init__(self, base: Path, passphrase: str | None) -> None:
        context = multiprocessing.get_context("spawn")
        self.channel, child_channel = context.Pipe()
        self.process: BaseProcess = context.Process(
            target=_store_process, args=(child_channel, str(base), passphrase)
        )
        self.process.start()
        child_channel.close()
        try:
            self.expect("ready")
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> _Worker:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def send(self, operation: str, name: str = "", value: str = "") -> None:
        self.channel.send((operation, name, value))

    def expect(self, status: str) -> str | int:
        deadline = time.monotonic() + _WAIT
        while True:
            remaining = deadline - time.monotonic()
            assert remaining > 0 and self.channel.poll(remaining), (
                status,
                self.process.pid,
                self.process.exitcode,
            )
            message = cast(Message, self.channel.recv())
            assert message[0] != "error", message
            if message[0] == status:
                return message[1]
            assert message[0] in {"acquired", "contended"}, (status, message)

    def unlock(self) -> int:
        self.send("unlock")
        return cast(int, self.expect("done"))

    def terminate_holder(self) -> None:
        self.process.terminate()
        self.process.join(3)
        assert not self.process.is_alive()
        assert self.process.exitcode is not None and self.process.exitcode != 0

    def close(self) -> None:
        if self.process.is_alive():
            try:
                self.send("stop")
            except (BrokenPipeError, EOFError, OSError):
                pass
            self.process.join(1)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(3)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(3)
        assert not self.process.is_alive(), "synthetic child was not reaped"
        self.channel.close()
        self.process.close()


def _snapshot(base: Path) -> tuple[int, set[str], list[str]]:
    """Read committed state through an independent short-lived SQLite connection."""
    with closing(sqlite3.connect(base / "config.db")) as connection:
        row = connection.execute(
            "SELECT value FROM store_meta WHERE key='key_generation'"
        ).fetchone()
        generation = int(row[0]) if row is not None else 0
        names = {row[0] for row in connection.execute("SELECT name FROM secrets")}
        successful_sets = [
            row[0]
            for row in connection.execute(
                "SELECT secret_name FROM audit "
                "WHERE action='set' AND allowed=1 ORDER BY id"
            )
        ]
    return generation, names, successful_sets


def _seed(base: Path, passphrase: str | None) -> None:
    with SecureStore(base_dir=base) as store:
        store.unlock(passphrase)
        store.set("seed", "synthetic-seed", caller="seed")


def _verify_values(
    base: Path, passphrase: str | None, expected: dict[str, str]
) -> None:
    with SecureStore(base_dir=base) as independent:
        independent.unlock(passphrase)
        assert independent.verify_integrity()
        for name, value in expected.items():
            assert independent.get(name) == value


@pytest.mark.parametrize("passphrase", [None, "synthetic-process-passphrase"])
def test_contending_first_unlock_initializes_one_key_generation(
    tmp_path: Path, passphrase: str | None
) -> None:
    with ExitStack() as stack:
        holder = stack.enter_context(_Worker(tmp_path, passphrase))
        contender = stack.enter_context(_Worker(tmp_path, passphrase))
        assert not (tmp_path / "master.key").exists()
        assert not (tmp_path / "master.salt").exists()
        holder.send("first-unlock-holder")
        holder.expect("held")
        contender.send("unlock")
        assert contender.expect("contended") == "unlock"
        assert _snapshot(tmp_path) == (0, set(), [])
        holder.send("release")
        assert holder.expect("done") == 1
        assert contender.expect("done") == 1
        contender.send("set", "second", "second-value")
        assert contender.expect("done") == 1
    assert _snapshot(tmp_path) == (1, {"first", "second"}, ["first", "second"])
    assert (tmp_path / "master.key").exists() == (passphrase is None)
    assert (tmp_path / "master.salt").exists() == (passphrase is not None)
    _verify_values(
        tmp_path, passphrase, {"first": "first-value", "second": "second-value"}
    )


@pytest.mark.parametrize("passphrase", [None, "synthetic-process-passphrase"])
def test_contended_mutation_commits_secret_and_success_audit_together(
    tmp_path: Path, passphrase: str | None
) -> None:
    _seed(tmp_path, passphrase)
    with ExitStack() as stack:
        holder = stack.enter_context(_Worker(tmp_path, passphrase))
        contender = stack.enter_context(_Worker(tmp_path, passphrase))
        assert holder.unlock() == contender.unlock() == 1
        holder.send("transaction-holder")
        holder.expect("held")
        contender.send("set", "waiting", "waiting-value")
        assert contender.expect("contended") == "set"
        assert _snapshot(tmp_path) == (1, {"seed"}, ["seed"])
        holder.send("release")
        assert holder.expect("done") == contender.expect("done") == 1
    assert _snapshot(tmp_path) == (
        1,
        {"seed", "held", "waiting"},
        ["seed", "held", "waiting"],
    )
    _verify_values(
        tmp_path, passphrase, {"held": "held-value", "waiting": "waiting-value"}
    )


@pytest.mark.parametrize("passphrase", [None, "synthetic-process-passphrase"])
@pytest.mark.parametrize("stale_operation", ["set", "rotate"])
def test_rotation_fences_contending_stale_owner_until_explicit_refresh(
    tmp_path: Path, passphrase: str | None, stale_operation: str
) -> None:
    _seed(tmp_path, passphrase)
    with ExitStack() as stack:
        holder = stack.enter_context(_Worker(tmp_path, passphrase))
        contender = stack.enter_context(_Worker(tmp_path, passphrase))
        assert holder.unlock() == contender.unlock() == 1
        holder.send("rotation-holder")
        assert holder.expect("rotated-holding") == 2
        contender.send(stale_operation, "stale", "must-not-persist")
        assert contender.expect("contended") == stale_operation
        assert _snapshot(tmp_path) == (2, {"seed"}, ["seed"])
        holder.send("release")
        assert holder.expect("done") == 2
        assert contender.expect("stale") == stale_operation
        contender.send("get", "seed")
        assert contender.expect("stale") == "get"
        assert contender.unlock() == 2
        contender.send("set", "refreshed", "refreshed-value")
        assert contender.expect("done") == 2
        contender.send("rotate")
        assert contender.expect("done") == 3
        holder.send("get", "seed")
        assert holder.expect("stale") == "get"
        assert holder.unlock() == 3
    assert _snapshot(tmp_path) == (3, {"seed", "refreshed"}, ["seed", "refreshed"])
    _verify_values(
        tmp_path, passphrase, {"seed": "synthetic-seed", "refreshed": "refreshed-value"}
    )


@pytest.mark.parametrize("passphrase", [None, "synthetic-process-passphrase"])
def test_kernel_releases_process_lock_when_holder_exits(
    tmp_path: Path, passphrase: str | None
) -> None:
    _seed(tmp_path, passphrase)
    with ExitStack() as stack:
        holder = stack.enter_context(_Worker(tmp_path, passphrase))
        contender = stack.enter_context(_Worker(tmp_path, passphrase))
        assert holder.unlock() == contender.unlock() == 1
        holder.send("lock-holder")
        holder.expect("held")
        contender.send("set", "survivor", "surviving-value")
        assert contender.expect("contended") == "set"
        holder.terminate_holder()
        assert contender.expect("done") == 1
    assert _snapshot(tmp_path) == (1, {"seed", "survivor"}, ["seed", "survivor"])
    _verify_values(tmp_path, passphrase, {"survivor": "surviving-value"})
