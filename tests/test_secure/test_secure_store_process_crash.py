"""Acknowledged process death around real storage transactions and publication.

These schedules prove process-crash recovery; they do not simulate power loss.
"""

from __future__ import annotations

import base64
import json
import multiprocessing
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest

pytest.importorskip("cryptography")
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

import gunz_utils.ext.secure_store as store_module
from gunz_utils.ext.secure_store import SecureStore

pytestmark = [pytest.mark.integration, pytest.mark.slow]
_WAIT = 20.0
_OLD_PASSPHRASE = "synthetic-old-process-proof"
_NEW_PASSPHRASE = "synthetic-new-process-proof"
_VALUES = {"alpha": b"synthetic alpha", "beta": b"synthetic beta"}


@dataclass
class _Snapshot:
    metadata: dict[str, bytes]
    secrets: list[tuple[Any, ...]]
    audit: list[tuple[Any, ...]]

    @property
    def generation(self) -> int:
        return int(self.metadata["key_generation"])


def _snapshot(base: Path) -> _Snapshot:
    with closing(sqlite3.connect(base / "config.db", timeout=2.0)) as connection:
        return _Snapshot(
            dict(connection.execute("SELECT key, value FROM store_meta")),
            list(connection.execute("SELECT * FROM secrets ORDER BY name")),
            list(connection.execute("SELECT * FROM audit ORDER BY id")),
        )


def _checkpoint(control: Connection, boundary: str, store: SecureStore) -> None:
    control.send(("paused", boundary, os.getpid(), store._conn.in_transaction))
    control.recv()  # Parent kills the worker instead of releasing this barrier.
    raise RuntimeError("crash checkpoint unexpectedly released")


class _CommitCheckpoint:
    """Delegate every SQL operation; surround real COMMIT with a barrier."""

    def __init__(self, store: SecureStore, control: Connection, boundary: str) -> None:
        self.connection = store._conn
        self.store = store
        self.control = control
        self.boundary = boundary

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)

    def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
        if sql == "COMMIT" and self.boundary == "transaction":
            _checkpoint(self.control, self.boundary, self.store)
        cursor = self.connection.execute(sql, parameters)
        if sql == "COMMIT" and self.boundary == "committed":
            _checkpoint(self.control, self.boundary, self.store)
        return cursor


def _crash_worker(
    base: str,
    old_passphrase: str | None,
    new_passphrase: str | None,
    boundary: str,
    operation: str,
    control: Connection,
) -> None:
    try:
        with SecureStore(base) as store:
            store.unlock(old_passphrase)
            store._conn = cast(
                sqlite3.Connection, _CommitCheckpoint(store, control, boundary)
            )
            original_write = store._write_private
            original_promote = store._promote_pending_key_material
            original_replace = store_module.os.replace

            def staged(path: Path, data: bytes) -> None:
                original_write(path, data)
                if boundary == "staged" and path.name.startswith(".master."):
                    _checkpoint(control, boundary, store)

            def promoted(*, passphrase_mode: bool) -> None:
                original_promote(passphrase_mode=passphrase_mode)
                if boundary == "published":
                    _checkpoint(control, boundary, store)

            def replaced(source: Any, target: Any, **kwargs: Any) -> None:
                original_replace(source, target, **kwargs)
                if boundary == "replaced" and Path(source).name in {
                    ".master.key.pending",
                    ".master.salt.pending",
                }:
                    _checkpoint(control, boundary, store)

            with (
                patch.object(store, "_write_private", staged),
                patch.object(store, "_promote_pending_key_material", promoted),
                patch.object(store_module.os, "replace", replaced),
            ):
                if operation == "rotation":
                    store.rotate_master_key(new_passphrase, allow_mode_switch=True)
                else:
                    store.set("alpha", b"synthetic changed alpha", caller="writer")
            control.send(("unexpected completion",))
    except BaseException as exc:
        control.send(("error", type(exc).__name__, str(exc)))
    finally:
        control.close()


def _material_snapshot(base: Path) -> dict[str, bytes]:
    return {
        name: (base / name).read_bytes()
        for name in (
            "master.key",
            "master.salt",
            ".master.key.pending",
            ".master.salt.pending",
        )
        if (base / name).exists()
    }


def _verify_worker(
    base: str,
    passphrase: str | None,
    expected_values: dict[str, bytes],
    control: Connection,
    reject_policy: bool = False,
) -> None:
    try:
        with SecureStore(base) as store:
            material_before = _material_snapshot(Path(base))
            if reject_policy:
                store._conn.execute("DELETE FROM store_meta WHERE key='record_format'")
                try:
                    store.unlock(passphrase)
                except InvalidToken:
                    pass
                else:
                    raise AssertionError("damaged authenticated policy was accepted")
                assert not store.is_unlocked()
                if _material_snapshot(Path(base)) != material_before:
                    raise AssertionError(
                        "policy rejection changed primary/pending material"
                    )
                control.send(("policy rejected", 0))
                return
            try:
                store.unlock("synthetic incorrect process-proof passphrase")
            except (InvalidToken, RuntimeError):
                pass
            else:
                raise AssertionError("incorrect credentials were accepted")
            assert not store.is_unlocked()
            if _material_snapshot(Path(base)) != material_before:
                raise AssertionError(
                    "credential rejection changed primary/pending material"
                )
            store.unlock(passphrase)
            assert store.verify_integrity()
            assert not store._pending_key_path.exists()
            assert not store._pending_salt_path.exists()
            assert store._master_key_path.exists() is (passphrase is None), (
                "recovered primary key files do not match authenticated mode"
            )
            assert store._salt_path.exists() is (passphrase is not None), (
                "recovered primary salt files do not match authenticated mode"
            )
            for name, value in expected_values.items():
                assert store.get_bytes(name, caller="writer") == value
            try:
                store.get_bytes("alpha", caller="intruder")
            except PermissionError:
                pass
            else:
                raise AssertionError("recovered ACL permitted unauthorized read")
            store.set("future", b"synthetic future", caller="writer", acl=["writer"])
            # Same-mode rotation must work without a mode-switch opt-in.
            store.rotate_master_key(passphrase)
            assert store.verify_integrity()
            assert store.get_bytes("future", caller="writer") == b"synthetic future"
            control.send(("verified", store._key_generation))
    except BaseException as exc:
        control.send(("error", type(exc).__name__, str(exc)))
    finally:
        control.close()


def _stop(process: Any) -> None:
    if process.is_alive():
        process.kill()
    process.join(timeout=5.0)
    if process.is_alive():
        process.kill()
        process.join(timeout=5.0)
    assert not process.is_alive(), "worker could not be reaped"


def _kill_at_checkpoint(
    base: Path,
    old_passphrase: str | None,
    new_passphrase: str | None,
    boundary: str,
    operation: str,
) -> None:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=_crash_worker,
        args=(str(base), old_passphrase, new_passphrase, boundary, operation, child),
    )
    try:
        process.start()
        child.close()
        assert parent.poll(_WAIT), "worker did not acknowledge crash checkpoint"
        message = parent.recv()
        assert message[:2] == ("paused", boundary), message
        assert message[2] == process.pid
        assert message[3] is (boundary == "transaction")
        process.kill()
        process.join(timeout=5.0)
        assert not process.is_alive()
        assert process.exitcode != 0
    finally:
        if process.pid is not None:
            _stop(process)
        parent.close()
        child.close()
        process.close()


def _verify_recovery(
    base: Path,
    passphrase: str | None,
    values: dict[str, bytes],
    *,
    reject_policy: bool = False,
) -> int:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe()
    process = context.Process(
        target=_verify_worker,
        args=(str(base), passphrase, values, child, reject_policy),
    )
    try:
        process.start()
        child.close()
        assert parent.poll(_WAIT), "independent reopen/future-operation worker blocked"
        message = parent.recv()
        assert message[0] == ("policy rejected" if reject_policy else "verified"), (
            message
        )
        process.join(timeout=5.0)
        assert not process.is_alive()
        assert process.exitcode == 0
        return int(message[1])
    finally:
        if process.pid is not None:
            _stop(process)
        parent.close()
        child.close()
        process.close()


def _prepare(base: Path, passphrase: str | None) -> _Snapshot:
    with SecureStore(base) as store:
        store.unlock(passphrase)
        for name, value in _VALUES.items():
            store.set(name, value, caller="writer", acl=["writer", "reader"])
    return _snapshot(base)


def _fernet(base: Path, passphrase: str | None, *, pending: bool) -> Fernet:
    prefix = ".master." if pending else "master."
    suffix = ".pending" if pending else ""
    if passphrase is None:
        key = (base / f"{prefix}key{suffix}").read_bytes().strip()
        assert len(key) == 44
    else:
        salt = (base / f"{prefix}salt{suffix}").read_bytes()
        assert len(salt) == 16
        key = base64.urlsafe_b64encode(
            PBKDF2HMAC(
                algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000
            ).derive(passphrase.encode())
        )
    return Fernet(key)


def _assert_envelopes(
    snapshot: _Snapshot, fernet: Fernet, values: dict[str, bytes]
) -> None:
    decoded: dict[str, bytes] = {}
    for name, ciphertext, acl, _created, _updated in snapshot.secrets:
        raw = fernet.decrypt(ciphertext)
        assert raw.startswith(b"\x00GZENV1\x00")
        envelope = json.loads(raw[8:])
        assert envelope["name"] == name
        assert envelope["acl"] == acl == "writer,reader"
        decoded[name] = base64.b64decode(envelope["payload"], validate=True)
    assert decoded == values
    assert fernet.decrypt(snapshot.metadata["key_check"]).startswith(
        b"gunz-utils-secure-store-v2:strict"
    )


@pytest.mark.parametrize(
    "old_mode,new_mode",
    [
        ("file", "file"),
        ("passphrase", "passphrase"),
        ("file", "passphrase"),
        ("passphrase", "file"),
    ],
)
@pytest.mark.parametrize(
    "boundary", ["staged", "transaction", "committed", "replaced", "published"]
)
def test_rotation_recovers_after_acknowledged_process_death(
    tmp_path: Path,
    old_mode: str,
    new_mode: str,
    boundary: str,
) -> None:
    base = tmp_path / "store"
    old_passphrase = _OLD_PASSPHRASE if old_mode == "passphrase" else None
    new_passphrase = _NEW_PASSPHRASE if new_mode == "passphrase" else None
    before = _prepare(base, old_passphrase)
    _kill_at_checkpoint(base, old_passphrase, new_passphrase, boundary, "rotation")
    after = _snapshot(base)
    committed = boundary in {"committed", "replaced", "published"}
    assert after.generation == before.generation + int(committed)
    assert after.audit == before.audit, "rotation must not invent mutation audit events"
    if not committed:
        assert after == before, "uncommitted rotation must leave durable SQL unchanged"
    pending = boundary in {"staged", "transaction", "committed"}
    staged_name = (
        ".master.salt.pending" if new_passphrase is not None else ".master.key.pending"
    )
    assert (base / staged_name).exists() is pending
    recovered_passphrase = new_passphrase if committed else old_passphrase
    _assert_envelopes(
        after,
        _fernet(base, recovered_passphrase, pending=boundary == "committed"),
        _VALUES,
    )
    generation = _verify_recovery(base, recovered_passphrase, _VALUES)
    assert generation == after.generation + 1
    assert (base / "master.salt").exists() is (recovered_passphrase is not None)
    assert (base / "master.key").exists() is (recovered_passphrase is None)


@pytest.mark.parametrize("passphrase", [None, _OLD_PASSPHRASE])
@pytest.mark.parametrize("boundary", ["transaction", "committed"])
def test_mutation_secret_and_audit_commit_together_after_process_death(
    tmp_path: Path,
    passphrase: str | None,
    boundary: str,
) -> None:
    base = tmp_path / "store"
    before = _prepare(base, passphrase)
    _kill_at_checkpoint(base, passphrase, passphrase, boundary, "mutation")
    after = _snapshot(base)
    values = dict(_VALUES)
    assert after.generation == before.generation
    if boundary == "transaction":
        assert after == before
    else:
        values["alpha"] = b"synthetic changed alpha"
        assert after.audit[:-1] == before.audit
        assert len(after.audit) == len(before.audit) + 1
        assert after.audit[-1][2:] == ("writer", "set", "alpha", 1)
    _assert_envelopes(after, _fernet(base, passphrase, pending=False), values)
    assert _verify_recovery(base, passphrase, values) == after.generation + 1


@pytest.mark.parametrize(
    "old_passphrase,new_passphrase",
    [
        (None, _NEW_PASSPHRASE),
        (_OLD_PASSPHRASE, None),
    ],
)
def test_rejected_policy_preserves_material_after_interrupted_mode_switch(
    tmp_path: Path,
    old_passphrase: str | None,
    new_passphrase: str | None,
) -> None:
    base = tmp_path / "store"
    _prepare(base, old_passphrase)
    _kill_at_checkpoint(base, old_passphrase, new_passphrase, "replaced", "rotation")
    assert _verify_recovery(base, new_passphrase, _VALUES, reject_policy=True) == 0
