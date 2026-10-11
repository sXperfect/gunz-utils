"""Authentication-first partial mode publication and cleanup failure regressions."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest
from cryptography.fernet import InvalidToken

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.ext.secure_store import SecureStore


def _partial_switch(
    base: Path,
    *,
    to_passphrase: bool,
) -> str | None:
    old_credential = None if to_passphrase else "synthetic-old-passphrase"
    new_credential = "synthetic-new-passphrase" if to_passphrase else None
    with SecureStore(base_dir=base) as store:
        store.unlock(old_credential)
        store.set("secret", "synthetic-secret", acl=["reader"], caller="reader")

        def rename_then_fail(
            *,
            passphrase_mode: bool,
        ) -> None:
            if passphrase_mode:
                os.replace(store._pending_salt_path, store._salt_path)
            else:
                os.replace(store._pending_key_path, store._master_key_path)
            raise OSError("synthetic interruption after real rename")

        with patch.object(store, "_promote_pending_key_material", rename_then_fail):
            with pytest.raises(OSError, match="synthetic interruption"):
                store.rotate_master_key(new_credential, allow_mode_switch=True)
    assert (base / "master.key").exists()
    assert (base / "master.salt").exists()
    return new_credential


def _material(
    base: Path,
) -> dict[str, bytes]:
    names = ("master.key", "master.salt", ".master.key.pending", ".master.salt.pending")
    return {
        name: (base / name).read_bytes() for name in names if (base / name).exists()
    }


def _assert_recovered(
    base: Path,
    credential: str | None,
) -> None:
    with SecureStore(base_dir=base) as store:
        store.unlock(credential)
        assert store.verify_integrity()
        assert store.get("secret", caller="reader") == "synthetic-secret"
        with pytest.raises(PermissionError):
            store.get("secret", caller="outsider")
        assert store._key_generation == 2
        assert (base / "master.key").exists() == (credential is None)
        assert (base / "master.salt").exists() == (credential is not None)
        store.rotate_master_key(credential)
        assert store._key_generation == 3
        assert store.get("secret", caller="reader") == "synthetic-secret"


@pytest.mark.parametrize("to_passphrase", [False, True])
@pytest.mark.parametrize("rejection", ["credentials", "policy", "generation"])
def test_rejected_recovery_preserves_every_primary_and_pending_byte(
    tmp_path: Path,
    to_passphrase: bool,
    rejection: str,
) -> None:
    credential = _partial_switch(tmp_path, to_passphrase=to_passphrase)
    before = _material(tmp_path)
    expected_error: type[Exception] = InvalidToken
    if rejection == "credentials":
        credential = None if to_passphrase else "synthetic-old-passphrase"
    else:
        field = "record_format" if rejection == "policy" else "key_generation"
        with closing(sqlite3.connect(tmp_path / "config.db")) as connection:
            connection.execute(
                "UPDATE store_meta SET value=? WHERE key=?", (b"invalid", field)
            )
            connection.commit()
        if rejection == "generation":
            expected_error = RuntimeError
    with SecureStore(base_dir=tmp_path) as store:
        with pytest.raises(expected_error):
            store.unlock(credential)
        assert not store.is_unlocked()
    assert _material(tmp_path) == before


@pytest.mark.parametrize("to_passphrase", [False, True])
def test_cleanup_failure_preserves_current_material_and_retry_finishes(
    tmp_path: Path,
    to_passphrase: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = _partial_switch(tmp_path, to_passphrase=to_passphrase)
    before = _material(tmp_path)
    obsolete = tmp_path / ("master.key" if to_passphrase else "master.salt")
    original_unlink = Path.unlink

    def denied_unlink(
        path: Path,
        *,
        missing_ok: bool = False,
    ) -> None:
        if path == obsolete:
            raise PermissionError("synthetic obsolete-primary cleanup denied")
        original_unlink(path, missing_ok=missing_ok)

    with SecureStore(base_dir=tmp_path) as store:
        with monkeypatch.context() as scoped:
            scoped.setattr(Path, "unlink", denied_unlink)
            with pytest.raises(PermissionError, match="synthetic obsolete-primary"):
                store.unlock(credential)
    assert _material(tmp_path) == before
    _assert_recovered(tmp_path, credential)


@pytest.mark.parametrize("to_passphrase", [False, True])
def test_post_cleanup_fsync_failure_does_not_lose_committed_current_key(
    tmp_path: Path,
    to_passphrase: bool,
) -> None:
    credential = _partial_switch(tmp_path, to_passphrase=to_passphrase)
    current_name = "master.salt" if to_passphrase else "master.key"
    current = (tmp_path / current_name).read_bytes()
    with SecureStore(base_dir=tmp_path) as store:
        with patch.object(
            store, "_fsync_base_dir", side_effect=OSError("synthetic fsync")
        ):
            with pytest.raises(OSError, match="synthetic fsync"):
                store.unlock(credential)
    assert (tmp_path / current_name).read_bytes() == current
    assert len(_material(tmp_path)) == 1
    _assert_recovered(tmp_path, credential)
