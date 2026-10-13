"""Perpetual security & concurrency audit - PHASE 8 regression tests.

Each test exposes a concrete security defect in the audited modules (context,
deprecation, ext/secure_crypto, ext/secure_store, ext/observability_loguru).
Tests are written to FAIL ("red") against the current source and must pass only
after the corresponding production fix lands. Production code is intentionally
not modified.

Findings covered here:
1. ``SecureStore._validate_identity`` accepts control characters (newline, ESC,
   C0 control bytes) in ``caller`` and ACL entries even though
   ``_validate_secret_name`` rejects ``ord(c) < 0x20``, so a caller identity can
   inject forged lines into the persisted audit log.
2. ``SecureStore.list_keys`` does not enforce the locked-store invariant: after
   ``lock()`` it still returns every secret name/metadata, while every other
   read/write method raises ``RuntimeError``. An unauthenticated caller with
   database file access can enumerate secret names without the key.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import tempfile

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.ext.secure_store import SecureStore


def _fresh_store() -> SecureStore:
    directory = tempfile.mkdtemp()
    store = SecureStore(base_dir=directory)
    store.unlock()
    return store


# -----------------------------------------------------------------------------
# secure_store.py - _validate_identity accepts control characters
# -----------------------------------------------------------------------------


def test_secure_store_identity_rejects_control_characters() -> None:
    """``_validate_identity`` must reject control characters in caller/ACL ids.

    ``_validate_secret_name`` (secure_store.py:623-634) rejects any character
    with ``ord(c) < 0x20``, but ``_validate_identity`` (secure_store.py:637-666)
    only rejects ``","`` and NUL, so a caller or ACL entry may contain a newline,
    escape, or other C0 control byte. This is an asymmetric validation gap: the
    identifier is persisted verbatim into the ``audit`` table and ACL column.
    """
    with pytest.raises(ValueError):
        SecureStore._validate_identity("ali\x01ce", field="caller")
    with pytest.raises(ValueError):
        SecureStore._validate_identity("bob\nline", field="ACL entry caller")
    with pytest.raises(ValueError):
        SecureStore._validate_identity("legit\x1b[31mce", field="caller")


def test_secure_store_caller_cannot_forge_audit_entries() -> None:
    """A control-character caller must not be persisted into the audit log.

    A ``caller`` identity containing a newline is stored verbatim in the audit
    table (``_audit`` -> ``audit_events``), letting the caller forge arbitrary
    audit-log lines (log injection) despite the store otherwise defending log
    context against control characters.
    """
    store = _fresh_store()
    try:
        with pytest.raises(ValueError):
            store.set(
                "kinj",
                "secret",
                caller="legit\n[FAKE] forged audit entry",
            )
    finally:
        store.close()


# -----------------------------------------------------------------------------
# secure_store.py - list_keys bypasses the locked-store invariant
# -----------------------------------------------------------------------------


def test_secure_store_list_keys_requires_unlock() -> None:
    """``list_keys`` must refuse to enumerate names on a locked store.

    Every other read/write method (``get``, ``get_bytes``, ``set``, ``delete``,
    ``verify_integrity``) raises ``RuntimeError`` when ``_fernet is None``, but
    ``list_keys`` (secure_store.py:1492-1518) returns all secret names and ACL
    metadata with no locked check, leaking the secret inventory to an
    unauthenticated caller who has filesystem/database access but not the key.
    """
    store = _fresh_store()
    try:
        store.set("api_token", "secret-value")
        store.set("db_pass", "hunter2")
        store.lock()
        assert not store.is_unlocked()
        with pytest.raises(RuntimeError, match="locked"):
            store.list_keys()
    finally:
        store.close()


# -----------------------------------------------------------------------------
# secure_store.py - locked invariant still enforced elsewhere (sanity green)
# -----------------------------------------------------------------------------


def test_secure_store_get_bytes_still_requires_unlock() -> None:
    """Sanity green: decryption reads keep refusing to run while locked."""
    store = _fresh_store()
    try:
        store.set("k", "v")
        store.lock()
        with pytest.raises(RuntimeError, match="locked"):
            store.get_bytes("k")
    finally:
        store.close()
