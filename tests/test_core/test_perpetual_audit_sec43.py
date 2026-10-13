"""Phase 43 (security lane) perpetual-audit tests.

Scope (optional ext modules): secure_crypto, secure_store, observability_loguru.

Finding (RED):
  1. observability_loguru.setup_logging (observability_loguru.py:136-139) logs
     the symlinked-log-file refusal with ``%s``-style formatting, but loguru
     uses ``{}``-style (str.format) formatting. The ``log_path`` argument is
     therefore dropped and the literal ``%s`` appears in the emitted warning,
     so the operator is never told which path was refused. This defeats the
     diagnostic intent of the guard (the whole point of the message is to name
     the unsafe symlink target).

secure_crypto and secure_store are audited and found already correct (GREEN
pins below exercise the security properties without weakening AEAD/
authenticity: random-IV AEAD roundtrip, wrong-key InvalidTag, ciphertext/tag
tamper rejection, plaintext-downgrade fail-closed, malformed-format rejection;
file-mode roundtrip, ACL enforcement, DB-ciphertext tamper detection,
key-rotation re-encryption, file/passphrase mode-mismatch fail-closed, and
audit log carrying no secret values).
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.fernet import InvalidToken

from gunz_utils.ext.observability_loguru import (
    _safe_session_id,
    _validate_log_name,
    setup_logging,
)
from gunz_utils.ext.secure_crypto import decrypt, encrypt
from gunz_utils.ext.secure_store import SecureStore

# ---------------------------------------------------------------------------
# RED: observability_loguru drops the refused log path from its warning
# ---------------------------------------------------------------------------

def test_loguru_symlink_warning_reports_the_refused_path() -> None:
    root = Path(tempfile.mkdtemp())
    (root / "logs").mkdir()
    log_path = root / "logs" / "app.log"
    os.symlink("/etc/hostname", str(log_path))

    buffer = io.StringIO()
    with contextlib.redirect_stderr(buffer):
        setup_logging("app", project_root=root)
    output = buffer.getvalue()

    # The whole point of the warning is to identify the unsafe target.
    assert str(log_path) in output
    assert "%s" not in output


# ---------------------------------------------------------------------------
# GREEN pins: secure_crypto
# ---------------------------------------------------------------------------

def test_secure_crypto_aead_roundtrip_and_wrong_key() -> None:
    ciphertext = encrypt("sensitive", passphrase="correct-horse")
    assert decrypt(ciphertext, passphrase="correct-horse") == "sensitive"
    with pytest.raises(InvalidTag):
        decrypt(ciphertext, passphrase="wrong-key")


def test_secure_crypto_rejects_tampered_ciphertext() -> None:
    ciphertext = encrypt("secret-value", passphrase="pw123")
    # Flip a hex digit in place (same length) so the payload parses but the
    # authentication tag no longer verifies -> AEAD must reject.
    tampered = ciphertext[:-1] + ("0" if ciphertext[-1] != "0" else "1")
    with pytest.raises(InvalidTag):
        decrypt(tampered, passphrase="pw123")


def test_secure_crypto_plaintext_downgrade_fails_closed() -> None:
    with pytest.raises(ValueError):
        decrypt("plaintext-data", passphrase="pw")
    # Opt-in migration path still requires explicit flag.
    assert decrypt("plaintext-data", passphrase="pw", allow_plaintext=True) == (
        "plaintext-data"
    )


def test_secure_crypto_rejects_malformed_and_legacy_formats() -> None:
    for bad in ["", "aes256:short", "aes256:v2:zz", "aes256:legacy-format"]:
        with pytest.raises(ValueError):
            decrypt(bad, passphrase="pw")


def test_secure_crypto_nonces_are_unique_per_encryption() -> None:
    values = {encrypt("same", passphrase="pw") for _ in range(10)}
    assert len(values) == 10


# ---------------------------------------------------------------------------
# GREEN pins: secure_store
# ---------------------------------------------------------------------------

def _fresh_store() -> tuple[SecureStore, Path]:
    directory = Path(tempfile.mkdtemp())
    store = SecureStore(base_dir=directory)
    store.unlock()
    return store, directory


def test_secure_store_file_mode_roundtrip_and_acl() -> None:
    store, _ = _fresh_store()
    store.set("api_key", "sk-123", caller="mcp", acl=["mcp", "cli"])
    assert store.get("api_key", caller="mcp") == "sk-123"
    with pytest.raises(PermissionError):
        store.get("api_key", caller="other")
    store.close()


def test_secure_store_tamper_detection() -> None:
    store, _ = _fresh_store()
    store.set("a", "value-a", caller="mcp", acl=["mcp"])
    row = store._conn.execute(
        "SELECT ciphertext FROM secrets WHERE name='a'"
    ).fetchone()
    corrupted = bytearray(row["ciphertext"])
    corrupted[5] ^= 0xFF
    store._conn.execute(
        "UPDATE secrets SET ciphertext=? WHERE name='a'", (bytes(corrupted),)
    )
    store._conn.commit()
    with pytest.raises(InvalidToken):
        store.verify_integrity()
    store.close()


def test_secure_store_rotate_master_key_reencrypts() -> None:
    store, _ = _fresh_store()
    store.set("a", "val-a", caller="mcp", acl=["mcp"])
    store.rotate_master_key()
    assert store.get("a", caller="mcp") == "val-a"
    store.close()


def test_secure_store_mode_mismatch_fails_closed() -> None:
    store, _ = _fresh_store()
    store.set("b", "v")
    with pytest.raises(RuntimeError):
        store.unlock(passphrase="pw")
    store.close()


def test_secure_store_audit_log_has_no_secret_values() -> None:
    store, _ = _fresh_store()
    store.set("tok", "SUPERSECRETVALUE")
    for event in store.audit_events():
        assert "SUPERSECRETVALUE" not in str(event)
    store.close()


# ---------------------------------------------------------------------------
# GREEN pins: observability_loguru
# ---------------------------------------------------------------------------

def test_observability_session_id_sanitizes_control_characters() -> None:
    assert "\n" not in _safe_session_id("a\nb")
    assert "\r" not in _safe_session_id("a\rb")
    assert "\x1b" not in _safe_session_id("a\x1b[31m")
    assert _safe_session_id("") == "GLOBAL"
    assert _safe_session_id(None) == "GLOBAL"
    assert len(_safe_session_id("x" * 500)) <= 128


def test_observability_log_name_validation() -> None:
    _validate_log_name("ok-name-1.x")
    for bad in ["../evil", "a/b", "..", ".", "", "a" * 129]:
        with pytest.raises(ValueError):
            _validate_log_name(bad)


def test_observability_refuses_symlinked_log_directory() -> None:
    root = Path(tempfile.mkdtemp())
    target = Path(tempfile.mkdtemp())
    os.symlink(str(target), str(root / "logs"))
    with pytest.raises(ValueError):
        setup_logging("app", project_root=root)


def test_observability_skips_symlinked_log_file_without_writing_through() -> None:
    root = Path(tempfile.mkdtemp())
    (root / "logs").mkdir()
    os.symlink("/etc/hostname", str(root / "logs" / "app.log"))
    setup_logging("app", project_root=root)
    # The guard must refuse rather than replace the symlink with a real file.
    assert (root / "logs" / "app.log").is_symlink()
