"""Adversarial SecureStore proofs for the A1 algorithm audit."""

from __future__ import annotations

import concurrent.futures
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.fernet import InvalidToken

from gunz_utils.ext.secure_store import SecureStore


def test_set_many_rolls_back_data_and_audit_on_mid_batch_failure(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()
        with pytest.raises(TypeError, match="str or bytes"):
            store.set_many(
                {
                    "first": "ok",
                    "bad": object(),  # type: ignore[dict-item]
                }
            )

        assert store.audit_events() == []
        assert store.get("first") is None
    finally:
        store.close()


def test_secure_store_validates_names_acl_and_audit_limit(tmp_path: Path) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()

        for name in ("", "   "):
            with pytest.raises(ValueError, match="name"):
                store.set(name, "value")

        with pytest.raises(ValueError, match="caller"):
            store.set("key", "value", caller="bad,caller")

        with pytest.raises(ValueError, match="caller"):
            store.set("key", "value", acl=["valid", "bad,caller"])

        with pytest.raises(ValueError, match="acl"):
            store.set("key", "value", acl=("caller",))  # type: ignore[arg-type]

        for limit in (0, 10_001, True, 1.5):
            with pytest.raises(ValueError, match="limit"):
                store.audit_events(limit=limit)  # type: ignore[arg-type]
    finally:
        store.close()


def test_file_key_rotation_round_trip_survives_reopen(tmp_path: Path) -> None:
    store = SecureStore(base_dir=tmp_path)
    store.unlock()
    store.set("secret", "value")
    old_key = store._master_key_path.read_bytes()

    store.rotate_master_key()
    new_key = store._master_key_path.read_bytes()

    assert new_key != old_key
    assert store.get("secret") == "value"
    store.close()

    reopened = SecureStore(base_dir=tmp_path)
    try:
        reopened.unlock()
        assert reopened.get("secret") == "value"
    finally:
        reopened.close()


def test_rotation_file_key_to_passphrase_and_back(tmp_path: Path) -> None:
    store = SecureStore(base_dir=tmp_path)
    store.unlock()
    store.set("secret", "value")

    store.rotate_master_key(
        new_passphrase="new-passphrase", allow_mode_switch=True
    )
    assert store._salt_path.is_file()
    assert not store._master_key_path.exists()
    store.close()

    passphrase_store = SecureStore(base_dir=tmp_path)
    passphrase_store.unlock(passphrase="new-passphrase")
    assert passphrase_store.get("secret") == "value"

    passphrase_store.rotate_master_key(allow_mode_switch=True)
    assert passphrase_store._master_key_path.is_file()
    assert not passphrase_store._salt_path.exists()
    passphrase_store.close()

    file_store = SecureStore(base_dir=tmp_path)
    try:
        file_store.unlock()
        assert file_store.get("secret") == "value"
    finally:
        file_store.close()


def test_rotation_database_failure_rolls_back_and_removes_pending_material(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()
        store.set("secret", "value")
        old_key = store._master_key_path.read_bytes()
        store._conn.execute(
            """
            CREATE TRIGGER fail_secret_update
            BEFORE UPDATE ON secrets
            BEGIN
                SELECT RAISE(ABORT, 'forced rotation failure');
            END
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            store.rotate_master_key()

        assert store._master_key_path.read_bytes() == old_key
        assert not store._pending_key_path.exists()
        assert not store._pending_salt_path.exists()
        assert store.get("secret") == "value"
    finally:
        store.close()


def test_rotation_publication_failure_recovers_from_pending_key(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    store.unlock()
    store.set("secret", "value")

    with patch.object(
        store,
        "_promote_pending_key_material",
        side_effect=OSError("publish failed"),
    ):
        with pytest.raises(OSError, match="publish failed"):
            store.rotate_master_key()

    assert store.get("secret") == "value"
    assert store._pending_key_path.is_file()
    store.close()

    reopened = SecureStore(base_dir=tmp_path)
    try:
        reopened.unlock()
        assert reopened.get("secret") == "value"
        assert not reopened._pending_key_path.exists()
    finally:
        reopened.close()


def test_wrong_old_key_does_not_mask_pending_rotation_recovery(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    store.unlock()
    store.set("secret", "value")

    with patch.object(
        store,
        "_promote_pending_key_material",
        side_effect=OSError("publish failed"),
    ):
        with pytest.raises(OSError):
            store.rotate_master_key()
    store.close()

    reopened = SecureStore(base_dir=tmp_path)
    try:
        reopened.unlock()
        assert reopened.get("secret") == "value"
    finally:
        reopened.close()


def test_secure_store_serializes_concurrent_access(tmp_path: Path) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()

        def write_and_read(index: int) -> str | None:
            name = f"key-{index}"
            value = f"value-{index}"
            store.set(name, value)
            return store.get(name)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(write_and_read, range(32)))

        assert results == [f"value-{index}" for index in range(32)]
        assert len(store.list_keys()) == 32
    finally:
        store.close()


def test_passphrase_unlock_rejects_empty_or_wrong_passphrase(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    store.unlock(passphrase="correct")
    store.set("secret", "value")
    store.close()

    reopened = SecureStore(base_dir=tmp_path)
    try:
        with pytest.raises(ValueError, match="passphrase"):
            reopened.unlock(passphrase="")
        with pytest.raises(InvalidToken):
            reopened.unlock(passphrase="wrong")
    finally:
        reopened.close()


def test_passphrase_rotation_publication_failure_recovers_pending_salt(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    store.unlock()
    store.set("secret", "value")

    with patch.object(
        store,
        "_promote_pending_key_material",
        side_effect=OSError("publish failed"),
    ):
        with pytest.raises(OSError, match="publish failed"):
            store.rotate_master_key(
                new_passphrase="new-passphrase", allow_mode_switch=True
            )

    assert store._pending_salt_path.is_file()
    store.close()

    reopened = SecureStore(base_dir=tmp_path)
    try:
        reopened.unlock(passphrase="new-passphrase")
        assert reopened.get("secret") == "value"
        assert reopened._salt_path.is_file()
        assert not reopened._master_key_path.exists()
        assert not reopened._pending_salt_path.exists()
    finally:
        reopened.close()


def test_stale_instance_fails_closed_after_rotation(tmp_path: Path) -> None:
    store1 = SecureStore(base_dir=tmp_path)
    store2 = SecureStore(base_dir=tmp_path)
    try:
        store1.unlock()
        store2.unlock()
        store1.set("secret", "original_value")
        assert store2.get("secret") == "original_value"

        # Rotate key using store1
        store1.rotate_master_key()
        store1.set("secret", "updated_after_rotation")

        # Stale store2 write must fail closed
        with pytest.raises(RuntimeError, match="stale"):
            store2.set("secret", "stale_write")

        # Stale store2 read must fail closed
        with pytest.raises(RuntimeError, match="stale"):
            store2.get("secret")

        # Value in store1 remains unchanged and uncorrupted
        assert store1.get("secret") == "updated_after_rotation"

        # After re-unlocking, store2 functions normally
        store2.unlock()
        assert store2.get("secret") == "updated_after_rotation"
    finally:
        store1.close()
        store2.close()


def test_rotation_prevents_unintended_mode_switch(tmp_path: Path) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()
        store.set("key1", "val1")

        # File-key store rotating to passphrase without allow_mode_switch must fail
        with pytest.raises(ValueError, match="allow_mode_switch"):
            store.rotate_master_key(new_passphrase="passphrase-1")

        # With allow_mode_switch=True, it succeeds
        store.rotate_master_key(
            new_passphrase="passphrase-1", allow_mode_switch=True
        )

        # Passphrase store rotating without passphrase and allow_mode_switch fails
        with pytest.raises(ValueError, match="allow_mode_switch"):
            store.rotate_master_key()

        # With allow_mode_switch=True, it converts back to file-key
        store.rotate_master_key(allow_mode_switch=True)
        assert store.get("key1") == "val1"
    finally:
        store.close()


def test_tampered_acl_or_ciphertext_substitution_rejected(
    tmp_path: Path,
) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()
        store.set("secret_a", "val_a", acl=["admin"])
        store.set("secret_b", "val_b", acl=["guest"])

        assert store.get("secret_a", caller="admin") == "val_a"
        assert store.get("secret_b", caller="guest") == "val_b"

        # 1. Tamper ACL in database: change secret_a ACL to guest directly in SQLite
        store._conn.execute(
            "UPDATE secrets SET acl = 'guest' WHERE name = 'secret_a'"
        )
        with pytest.raises(InvalidToken):
            store.get("secret_a", caller="guest")

        # Restore secret_a ACL
        store._conn.execute(
            "UPDATE secrets SET acl = 'admin' WHERE name = 'secret_a'"
        )
        assert store.get("secret_a", caller="admin") == "val_a"

        # 2. Swap ciphertexts between secret_a and secret_b
        row_b = store._conn.execute(
            "SELECT ciphertext FROM secrets WHERE name = 'secret_b'"
        ).fetchone()
        store._conn.execute(
            "UPDATE secrets SET ciphertext = ? WHERE name = 'secret_a'",
            (row_b["ciphertext"],),
        )

        # secret_a now contains secret_b's ciphertext. Must fail envelope check!
        with pytest.raises(InvalidToken):
            store.get("secret_a", caller="admin")
    finally:
        store.close()


def test_verify_integrity(tmp_path: Path) -> None:
    store = SecureStore(base_dir=tmp_path)
    try:
        store.unlock()
        store.set("k1", "v1")
        store.set("k2", "v2", acl=["worker"])

        # Intact store verifies successfully
        assert store.verify_integrity() is True

        # Tampering with key_check causes verify_integrity to raise InvalidToken
        store._conn.execute(
            "UPDATE store_meta SET value = ? WHERE key = 'key_check'",
            (b"corrupted_marker",),
        )
        with pytest.raises(InvalidToken):
            store.verify_integrity()
    finally:
        store.close()

