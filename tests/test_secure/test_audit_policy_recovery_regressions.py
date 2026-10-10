"""Authenticated migration policy and durable rotation outcome regressions."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from cryptography.fernet import InvalidToken

from gunz_utils.ext.secure_store import SecureStore


def _legacy_store(base: Path) -> tuple[SecureStore, bytes]:
    store = SecureStore(base_dir=base)
    store.unlock()
    fernet = store.fernet
    assert fernet is not None
    token = fernet.encrypt(b"synthetic legacy value")
    store._conn.execute(
        "INSERT INTO secrets VALUES (?, ?, ?, ?, ?)",
        ("secret", token, "admin", 0.0, 0.0),
    )
    store._conn.execute(
        "UPDATE store_meta SET value = ? WHERE key = 'key_check'",
        (fernet.encrypt(b"gunz-utils-secure-store-v1"),),
    )
    store._conn.execute("DELETE FROM store_meta WHERE key = 'record_format'")
    store.lock()
    return store, token


@pytest.mark.parametrize("marker", [None, b"invalid", b"legacy"])
@pytest.mark.parametrize("operation", ["get", "set", "delete", "verify_integrity"])
def test_migrated_legacy_replay_cannot_downgrade_policy(
    tmp_path: Path, marker: bytes | None, operation: str
) -> None:
    store, token = _legacy_store(tmp_path)
    try:
        store.unlock(allow_legacy=True)
        assert store.migrate_records() == 1
        store._conn.execute(
            "UPDATE secrets SET ciphertext = ?, acl = '' WHERE name = 'secret'",
            (token,),
        )
        if marker is None:
            store._conn.execute("DELETE FROM store_meta WHERE key = 'record_format'")
        else:
            store._conn.execute(
                "UPDATE store_meta SET value = ? WHERE key = 'record_format'", (marker,)
            )
        with pytest.raises(InvalidToken):
            if operation == "verify_integrity":
                store.verify_integrity()
            elif operation == "set":
                store.set("secret", "replacement", caller="outsider")
            else:
                getattr(store, operation)("secret", caller="outsider")
    finally:
        store.close()


@pytest.mark.parametrize("allow_legacy", [False, True])
def test_modern_policy_corruption_rejected_on_reopen(
    tmp_path: Path, allow_legacy: bool
) -> None:
    with SecureStore(base_dir=tmp_path) as store:
        store.unlock()
        store.set("secret", "value")
        store._conn.execute("DELETE FROM store_meta WHERE key = 'record_format'")
    with SecureStore(base_dir=tmp_path) as reopened:
        with pytest.raises(InvalidToken):
            reopened.unlock(allow_legacy=allow_legacy)


def test_trusted_legacy_upgrade_requires_explicit_opt_in(tmp_path: Path) -> None:
    store, _ = _legacy_store(tmp_path)
    try:
        with pytest.raises(InvalidToken, match="explicit trusted"):
            store.unlock()
        store.unlock(allow_legacy=True)
        assert store.get("secret", caller="admin") == "synthetic legacy value"
        assert store.migrate_records() == 1
        store.rotate_master_key()
        assert store.verify_integrity()
    finally:
        store.close()
    with SecureStore(base_dir=tmp_path) as reopened:
        reopened.unlock()
        assert reopened._records_strict()
        assert reopened.get("secret", caller="admin") == "synthetic legacy value"


def test_v1_strict_store_upgrades_without_legacy_opt_in(tmp_path: Path) -> None:
    with SecureStore(base_dir=tmp_path) as store:
        store.unlock()
        store.set("secret", "value")
        assert store.fernet is not None
        store._conn.execute(
            "UPDATE store_meta SET value = ? WHERE key = 'key_check'",
            (store.fernet.encrypt(b"gunz-utils-secure-store-v1"),),
        )
    with SecureStore(base_dir=tmp_path) as reopened:
        reopened.unlock()
        assert reopened._records_strict()
        assert reopened.get("secret") == "value"


class _RotationFailureConnection:
    def __init__(
        self, conn: sqlite3.Connection, *, durable_commit: bool, fail_body: bool = False
    ) -> None:
        self.conn = conn
        self.durable_commit = durable_commit
        self.fail_body = fail_body
        self.rollback_attempted = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self.conn, name)

    def execute(self, sql: str, *args: Any) -> Any:
        if sql == "ROLLBACK":
            self.rollback_attempted = True
            raise sqlite3.OperationalError("secondary rollback failure")
        if sql == "COMMIT":
            if self.durable_commit:
                self.conn.execute(sql)
            raise sqlite3.OperationalError("original commit failure")
        return self.conn.execute(sql, *args)

    def executemany(self, sql: str, values: Any) -> Any:
        if self.fail_body:
            raise sqlite3.OperationalError("original body failure")
        return self.conn.executemany(sql, values)


@pytest.mark.parametrize(
    "durable_commit,fail_body", [(False, False), (True, False), (False, True)]
)
def test_rotation_recovers_durable_state_and_preserves_original_error(
    tmp_path: Path, durable_commit: bool, fail_body: bool
) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()
        store.set("secret", "value")
        old_generation = store._key_generation
        proxy = _RotationFailureConnection(
            store._conn, durable_commit=durable_commit, fail_body=fail_body
        )
        store._conn = proxy  # type: ignore[assignment]
        expected = "original body failure" if fail_body else "original commit failure"
        with pytest.raises(sqlite3.OperationalError, match=expected):
            store.rotate_master_key()
        assert proxy.rollback_attempted == (not durable_commit)
        assert not store._conn.in_transaction
        assert store._key_generation == old_generation + int(durable_commit)
        assert store._pending_key_path.exists() == durable_commit
        assert store.get("secret") == "value"
        store.set("subsequent", "persisted")
        with SecureStore(base_dir=tmp_path) as independent:
            independent.unlock()
            assert independent.verify_integrity()
            assert independent.get("secret") == "value"
            assert independent.get("subsequent") == "persisted"
    finally:
        store.close()


def test_unknown_recovery_state_locks_store_and_keeps_pending_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with SecureStore(base_dir=tmp_path) as store:
        store.unlock()
        proxy = _RotationFailureConnection(store._conn, durable_commit=False)
        store._conn = proxy  # type: ignore[assignment]

        def fail_reconnect() -> None:
            raise sqlite3.OperationalError("secondary reconnect failure")

        monkeypatch.setattr(store, "_reconnect_database", fail_reconnect)
        with pytest.raises(
            sqlite3.OperationalError, match="original commit failure"
        ) as error:
            store.rotate_master_key()
        assert not store.is_unlocked()
        assert store._pending_key_path.exists()
        assert "pending key material retained" in error.value.__notes__[0]


def test_second_rotation_preserves_committed_unpublished_key(tmp_path: Path) -> None:
    with SecureStore(base_dir=tmp_path) as store:
        store.unlock()
        store.set("secret", "value")
        store._conn = _RotationFailureConnection(  # type: ignore[assignment]
            store._conn, durable_commit=True
        )
        with pytest.raises(sqlite3.OperationalError, match="original commit failure"):
            store.rotate_master_key()
        assert store._pending_key_path.exists()
        store._conn = _RotationFailureConnection(  # type: ignore[assignment]
            store._conn, durable_commit=False, fail_body=True
        )
        with pytest.raises(sqlite3.OperationalError, match="original body failure"):
            store.rotate_master_key()
        assert not store._pending_key_path.exists()
    with SecureStore(base_dir=tmp_path) as reopened:
        reopened.unlock()
        assert reopened.get("secret") == "value"
