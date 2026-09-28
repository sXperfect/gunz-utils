"""A1 transaction, concurrency, and recovery proofs for SecureStore."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from gunz_utils.ext.secure_store import SecureStore


def _store(path: Path) -> SecureStore:
    store = SecureStore(base_dir=path)
    store.unlock()
    return store


def test_set_rolls_back_secret_if_success_audit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path / "store")
    try:
        store.set("key", "old")
        original_audit = store._audit

        def fail_success_audit(
            caller: str,
            action: str,
            secret_name: str | None,
            allowed: bool,
        ) -> None:
            if action == "set" and allowed:
                raise sqlite3.OperationalError("audit unavailable")
            original_audit(caller, action, secret_name, allowed)

        monkeypatch.setattr(store, "_audit", fail_success_audit)
        with pytest.raises(sqlite3.OperationalError, match="audit unavailable"):
            store.set("key", "new")

        monkeypatch.setattr(store, "_audit", original_audit)
        assert store.get("key") == "old"
    finally:
        store.close()


def test_delete_rolls_back_if_success_audit_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path / "store")
    try:
        store.set("key", "value")
        original_audit = store._audit

        def fail_success_audit(
            caller: str,
            action: str,
            secret_name: str | None,
            allowed: bool,
        ) -> None:
            if action == "delete" and allowed:
                raise sqlite3.OperationalError("audit unavailable")
            original_audit(caller, action, secret_name, allowed)

        monkeypatch.setattr(store, "_audit", fail_success_audit)
        with pytest.raises(sqlite3.OperationalError, match="audit unavailable"):
            store.delete("key")

        monkeypatch.setattr(store, "_audit", original_audit)
        assert store.get("key") == "value"
    finally:
        store.close()


def test_set_many_is_all_or_nothing_and_records_batch_denial(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "store")
    try:
        store.set(
            "protected",
            "original",
            caller="owner",
            acl=["owner"],
        )

        with pytest.raises(PermissionError):
            store.set_many(
                {
                    "new": "must-roll-back",
                    "protected": "forbidden",
                },
                caller="library",
            )

        assert {item.name for item in store.list_keys(acl_filter=False)} == {
            "protected"
        }
        assert store.get("protected", caller="owner") == "original"

        events = store.audit_events(limit=20)
        assert any(
            event["action"] == "set_many"
            and event["allowed"] == 0
            for event in events
        )
    finally:
        store.close()


def test_set_many_validates_entire_batch_before_mutation(tmp_path: Path) -> None:
    store = _store(tmp_path / "store")
    try:
        with pytest.raises(TypeError, match="str or bytes"):
            store.set_many(
                {
                    "first": "value",
                    "bad": object(),  # type: ignore[dict-item]
                }
            )

        assert store.list_keys(acl_filter=False) == []
    finally:
        store.close()


def test_concurrent_threads_are_serialized_without_lost_updates(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "store")
    try:
        def write(index: int) -> None:
            store.set(f"key-{index}", f"value-{index}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(write, index)
                for index in range(32)
            ]
            for future in futures:
                future.result()

        names = {item.name for item in store.list_keys(acl_filter=False)}
        assert names == {f"key-{index}" for index in range(32)}
        for index in range(32):
            assert store.get(f"key-{index}") == f"value-{index}"
    finally:
        store.close()


def test_rotation_recovers_from_key_publication_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = tmp_path / "store"
    store = _store(base)
    store.set("key", "value")

    def fail_publication(*, passphrase_mode: bool) -> None:
        assert not passphrase_mode
        raise OSError("publication failed")

    monkeypatch.setattr(
        store,
        "_promote_pending_key_material",
        fail_publication,
    )

    with pytest.raises(OSError, match="publication failed"):
        store.rotate_master_key()

    assert store._pending_key_path.is_file()
    store.close()

    recovered = SecureStore(base_dir=base)
    try:
        recovered.unlock()
        assert recovered.get("key") == "value"
        assert recovered._master_key_path.is_file()
        assert not recovered._pending_key_path.exists()
    finally:
        recovered.close()


def test_successful_bulk_transaction_commits_audit_with_values(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path / "store")
    try:
        store.set_many({"a": "1", "b": b"2"})
        assert store.get("a") == "1"
        assert store.get_bytes("b") == b"2"

        events = store.audit_events(limit=20)
        assert any(
            event["action"] == "set_many"
            and event["allowed"] == 1
            for event in events
        )
        assert all("value" not in event for event in events)
        assert all("ciphertext" not in event for event in events)
    finally:
        store.close()
