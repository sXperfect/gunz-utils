"""Fernet-encrypted credential store with ACLs and audit log.

Promoted from ``libs/hyperhedron-google/src/hyperhedron_google/secure_store.py``
on 2026-06-26 (Phase 6.1 of the gunz-youtrack secure-config task). The
implementation is byte-identical; only the ``DEFAULT_BASE_DIR`` was
parameterised so each consumer library (``gunz-youtrack``,
``hyperhedron-google``, future wrappers) can use its own XDG directory.

Layout (per consumer)::
    ~/.config/<library-name>/
        master.key          Fernet key (mode 0600). File-mode only.
        master.salt         PBKDF2 salt (mode 0600). Passphrase-mode only.
        config.db           SQLite: encrypted secret rows + audit log.

Two unlock modes:

    file (default):   reads master.key directly (server/headless).
    passphrase:       derives master.key from a user passphrase +
                      a salt (laptop / interactive).

Secrets are Fernet-encrypted (AES-128-CBC + HMAC-SHA256) at rest.
Each secret has an optional ACL list of caller IDs permitted to
read it (e.g. ``["mcp", "cli", "library"]``). Empty ACL = open access.

Example (file mode)::
    >>> store = SecureStore()  # uses default ~/.config/<library>/
    >>> store.unlock()         # auto-generates master.key on first run
    >>> store.set("google.api_key", "AIza...")
    >>> store.get("google.api_key")
    'AIza...'

Example (passphrase mode)::
    >>> store = SecureStore()
    >>> store.unlock(passphrase="correct horse battery staple")
    Set master passphrase (will be required each time).
    >>> store.set("google.api_key", "AIza...", acl=["mcp"])
"""

from __future__ import annotations

import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation for SHA-256
_KEY_FILE_MODE = 0o600  # owner read/write only


def default_base_dir(library_name: str) -> Path:
    """Resolve the default XDG base directory for ``library_name``.

    Honours the ``HYPERHEDRON_CONFIG_DIR`` env var (overrides all
    libraries) for power users / CI; falls back to
    ``~/.config/<library_name>/`` per the XDG Base Directory spec.

    This function (not a module-level constant) is used because
    ``os.environ`` may not be populated at import time (tests, frozen
    apps). The legacy ``hyperhedron-google`` module-level constant
    ``DEFAULT_BASE_DIR`` evaluates ``os.environ`` exactly once at
    import; we keep that pattern by deferring the evaluation here.
    """
    override = os.environ.get("HYPERHEDRON_CONFIG_DIR")
    if override:
        return Path(override)
    return Path.home() / ".config" / library_name


@dataclass
class SecretMetadata:
    """Metadata about a stored secret (no value)."""

    name: str
    created_at: float
    updated_at: float
    acl: list[str]


class SecureStore:
    """Fernet-encrypted secret store with ACLs and audit log.

    Parameters
    ----------
    base_dir : str | Path | None
        Directory holding ``master.key``, ``master.salt``, ``config.db``.
        If ``None``, uses ``default_base_dir(library_name)`` where
        ``library_name`` defaults to ``"hyperhedron"``. Consumers
        should pass their own library name to keep config dirs
        separate (e.g. ``SecureStore(library_name="gunz-youtrack")``).

        Backward-compat: if ``base_dir`` is explicitly provided,
        ``library_name`` is ignored. This preserves the v1 API for
        `hyperhedron-google` callers.
    library_name : str
        Used to compute ``default_base_dir`` when ``base_dir`` is None.
        Default is ``"hyperhedron"`` for legacy callers; new code
        SHOULD pass an explicit library name (e.g.
        ``"gunz-youtrack"``).
    """

    def __init__(
        self,
        base_dir: str | Path | None = None,
        *,
        library_name: str = "hyperhedron",
    ) -> None:
        self._base_dir = (
            Path(base_dir) if base_dir else default_base_dir(library_name)
        )
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._master_key_path = self._base_dir / "master.key"
        self._salt_path = self._base_dir / "master.salt"
        self._db_path = self._base_dir / "config.db"
        self._lock = threading.Lock()
        self._fernet_lock = threading.Lock()
        self._fernet: Fernet | None = None
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS secrets (
                    name TEXT PRIMARY KEY,
                    ciphertext BLOB NOT NULL,
                    acl TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    caller TEXT NOT NULL,
                    action TEXT NOT NULL,
                    secret_name TEXT,
                    allowed INTEGER NOT NULL
                );
                """
            )

    def is_unlocked(self) -> bool:
        with self._fernet_lock:
            return self._fernet is not None

    @property
    def fernet(self) -> Fernet | None:
        """Thread-safe Fernet accessor; returns the current instance or None."""
        with self._fernet_lock:
            return self._fernet

    def unlock(self, passphrase: str | None = None) -> None:
        """Unlock the store. Auto-creates master key on first run."""
        if passphrase is None:
            if self._master_key_path.exists():
                key = self._master_key_path.read_bytes().strip()
            else:
                key = Fernet.generate_key()
                self._master_key_path.write_bytes(key)
                os.chmod(self._master_key_path, _KEY_FILE_MODE)
        else:
            if self._salt_path.exists():
                salt = self._salt_path.read_bytes()
            else:
                salt = os.urandom(16)
                self._salt_path.write_bytes(salt)
                os.chmod(self._salt_path, _KEY_FILE_MODE)
            import base64

            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=_PBKDF2_ITERATIONS,
                backend=default_backend(),
            )
            key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        with self._fernet_lock:
            self._fernet = Fernet(key)

    def _audit(
        self,
        caller: str,
        action: str,
        secret_name: str | None,
        allowed: bool,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit (timestamp, caller, action, secret_name, allowed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (time.time(), caller, action, secret_name, 1 if allowed else 0),
            )

    def set(
        self,
        name: str,
        value: str | bytes,
        *,
        caller: str = "library",
        acl: list[str] | None = None,
    ) -> None:
        """Encrypt and store a secret."""
        if not self.is_unlocked():
            raise RuntimeError("Store is locked. Call unlock() first.")
        with self._fernet_lock:
            fernet = self._fernet
        if fernet is None:
            raise RuntimeError("Store is locked. Call unlock() first.")

        if isinstance(value, str):
            value = value.encode()
        ciphertext = fernet.encrypt(value)
        acl_str = ",".join(acl) if acl else ""
        now = time.time()

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO secrets (name, ciphertext, acl, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    ciphertext = excluded.ciphertext,
                    acl = excluded.acl,
                    updated_at = excluded.updated_at
                """,
                (name, ciphertext, acl_str, now, now),
            )
        self._audit(caller, "set", name, True)

    def get(self, name: str, *, caller: str = "library") -> str | None:
        """Decrypt and return a secret, or None if not found."""
        with self._fernet_lock:
            fernet = self._fernet
        if fernet is None:
            raise RuntimeError("Store is locked. Call unlock() first.")

        with self._lock:
            cur = self._conn.execute(
                "SELECT ciphertext, acl FROM secrets WHERE name = ?",
                (name,),
            )
            row = cur.fetchone()

        if row is None:
            self._audit(caller, "get", name, False)
            return None

        acl = [s for s in (row["acl"] or "").split(",") if s]
        if acl and caller not in acl:
            self._audit(caller, "get", name, False)
            raise PermissionError(
                f"Caller {caller!r} not in ACL {acl} for secret {name!r}"
            )

        try:
            plaintext = fernet.decrypt(row["ciphertext"])
        except InvalidToken:
            self._audit(caller, "get", name, False)
            raise

        self._audit(caller, "get", name, True)
        return plaintext.decode()

    def delete(self, name: str, *, caller: str = "library") -> bool:
        """Delete a secret. Returns True if it existed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM secrets WHERE name = ?",
                (name,),
            )
            deleted = cur.rowcount > 0
        self._audit(caller, "delete", name, deleted)
        return deleted

    def list_keys(
        self, *, caller: str = "library", acl_filter: bool = True
    ) -> list[SecretMetadata]:
        """List secret names with metadata. Respects ACL by default."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT name, acl, created_at, updated_at FROM secrets"
            )
            rows = cur.fetchall()

        out: list[SecretMetadata] = []
        for r in rows:
            acl = [s for s in (r["acl"] or "").split(",") if s]
            if acl_filter and acl and caller not in acl:
                continue
            out.append(
                SecretMetadata(
                    name=r["name"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    acl=acl,
                )
            )
        return out

    def rotate_master_key(self, new_passphrase: str | None = None) -> None:
        """Re-encrypt all secrets with a new master key."""
        with self._fernet_lock:
            old_fernet = self._fernet
        if old_fernet is None:
            raise RuntimeError("Store is locked. Call unlock() first.")

        new_key = (
            Fernet.generate_key()
            if new_passphrase is None
            else self._derive_from_passphrase(new_passphrase)
        )
        new_fernet = Fernet(new_key)

        with self._lock:
            cur = self._conn.execute("SELECT name, ciphertext FROM secrets")
            rows = cur.fetchall()
            for r in rows:
                plaintext = old_fernet.decrypt(r["ciphertext"])
                new_ciphertext = new_fernet.encrypt(plaintext)
                self._conn.execute(
                    "UPDATE secrets SET ciphertext = ? WHERE name = ?",
                    (new_ciphertext, r["name"]),
                )

        if new_passphrase is None:
            self._master_key_path.write_bytes(new_key)
            os.chmod(self._master_key_path, _KEY_FILE_MODE)
        with self._fernet_lock:
            self._fernet = new_fernet

    def lock(self) -> None:
        """Atomically clear the Fernet instance. Thread-safe."""
        with self._fernet_lock:
            self._fernet = None

    def _derive_from_passphrase(self, passphrase: str) -> bytes:
        import base64

        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        salt = (
            self._salt_path.read_bytes()
            if self._salt_path.exists()
            else os.urandom(16)
        )
        if not self._salt_path.exists():
            self._salt_path.write_bytes(salt)
            os.chmod(self._salt_path, _KEY_FILE_MODE)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
            self._fernet = None


def main_unlock_interactive() -> SecureStore:
    """Convenience helper for CLI: prompts for passphrase if needed."""
    store = SecureStore()
    if store._master_key_path.exists() and store._salt_path.exists():
        import getpass

        pw = getpass.getpass("Master passphrase: ")
        store.unlock(passphrase=pw)
    else:
        store.unlock()
    return store


__all__ = [
    "SecretMetadata",
    "SecureStore",
    "default_base_dir",
    "main_unlock_interactive",
]


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        s = SecureStore()
        s.unlock()
        print(f"Initialized at {s._base_dir}")
        s.close()
    else:
        print(
            "Usage: python -m gunz_utils.secure_store init\n"
            "(For library-specific configs, use "
            "python -m gunz_youtrack.config init instead.)"
        )
