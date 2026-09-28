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

Two unlock modes::

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

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
import base64
import os
import re
import sqlite3
import stat
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .._version import __version__ as __version__

_PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation for SHA-256
_KEY_FILE_MODE = 0o600  # owner read/write only
_DIR_MODE = 0o700
_LIBRARY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


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
    if (
        not isinstance(library_name, str)
        or library_name in {".", ".."}
        or _LIBRARY_NAME_RE.fullmatch(library_name) is None
    ):
        raise ValueError("library_name must be a simple filesystem-safe name")
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
            Path(base_dir) if base_dir is not None else default_base_dir(library_name)
        )
        self._ensure_private_directory(self._base_dir)
        self._master_key_path = self._base_dir / "master.key"
        self._salt_path = self._base_dir / "master.salt"
        self._db_path = self._base_dir / "config.db"
        if self._db_path.is_symlink():
            raise ValueError("secure-store database path must not be a symlink")
        if self._db_path.exists() and not self._db_path.is_file():
            raise ValueError("secure-store database path must be a regular file")
        self._lock = threading.RLock()
        self._fernet_lock = self._lock
        self._fernet: Fernet | None = None
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()
        self._ensure_private_file(self._db_path)

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

                CREATE TABLE IF NOT EXISTS store_meta (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL
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

    @staticmethod
    def _ensure_private_directory(path: Path) -> None:
        """Create and verify an owner-private non-symlink directory."""
        if path.is_symlink():
            raise ValueError("secure-store base directory must not be a symlink")
        path.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
        info = os.stat(path, follow_symlinks=False)
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("secure-store base path must be a directory")
        if os.name == "posix":
            if info.st_uid != os.getuid():
                raise PermissionError("secure-store base directory has wrong owner")
            os.chmod(path, _DIR_MODE)
            if stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode) != _DIR_MODE:
                raise PermissionError("secure-store base directory is not mode 0700")

    @staticmethod
    def _ensure_private_file(path: Path) -> None:
        """Reject symlinks/non-files and enforce owner-only permissions."""
        if path.is_symlink():
            raise ValueError(f"private path must not be a symlink: {path.name}")
        info = os.stat(path, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"private path must be a regular file: {path.name}")
        if os.name == "posix":
            if info.st_uid != os.getuid():
                raise PermissionError(f"private file has wrong owner: {path.name}")
            os.chmod(path, _KEY_FILE_MODE)
            mode = stat.S_IMODE(os.stat(path, follow_symlinks=False).st_mode)
            if mode != _KEY_FILE_MODE:
                raise PermissionError(f"private file is not mode 0600: {path.name}")

    @classmethod
    def _read_private(cls, path: Path) -> bytes:
        cls._ensure_private_file(path)
        return path.read_bytes()

    @staticmethod
    def _validate_identity(value: str, *, field: str) -> str:
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 256
            or "," in value
            or "\x00" in value
        ):
            raise ValueError(
                f"{field} must be a non-empty identifier without commas or NULs"
            )
        return value

    @classmethod
    def _normalize_acl(cls, acl: list[str] | None) -> list[str] | None:
        if acl is None:
            return None
        return [cls._validate_identity(item, field="ACL entry") for item in acl]

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        """Create or replace a private file without a world-readable window."""
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _KEY_FILE_MODE)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _verify_or_initialize_key(self, fernet: Fernet) -> None:
        row = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = 'key_check'"
        ).fetchone()
        if row is not None:
            if fernet.decrypt(row["value"]) != b"gunz-utils-secure-store-v1":
                raise InvalidToken
            return
        secret = self._conn.execute(
            "SELECT ciphertext FROM secrets LIMIT 1"
        ).fetchone()
        if secret is not None:
            fernet.decrypt(secret["ciphertext"])
        token = fernet.encrypt(b"gunz-utils-secure-store-v1")
        self._conn.execute(
            "INSERT INTO store_meta(key, value) VALUES ('key_check', ?)", (token,)
        )

    def unlock(self, passphrase: str | None = None) -> None:
        """Unlock the store and verify the selected key before publishing it."""
        if passphrase is not None and (
            not isinstance(passphrase, str) or not passphrase
        ):
            raise ValueError("passphrase must be a non-empty string")
        with self._lock:
            if passphrase is None:
                if self._salt_path.exists() and not self._master_key_path.exists():
                    raise RuntimeError(
                        "Store is passphrase-protected; passphrase required"
                    )
                if self._master_key_path.exists():
                    key = self._read_private(self._master_key_path).strip()
                else:
                    key = Fernet.generate_key()
                    self._write_private(self._master_key_path, key)
            else:
                if self._master_key_path.exists() and not self._salt_path.exists():
                    raise RuntimeError(
                        "Store uses file-key mode; do not supply passphrase"
                    )
                if self._salt_path.exists():
                    salt = self._read_private(self._salt_path)
                else:
                    salt = os.urandom(16)
                    self._write_private(self._salt_path, salt)
                key = self._derive_key(passphrase, salt)
            candidate = Fernet(key)
            self._verify_or_initialize_key(candidate)
            self._fernet = candidate

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        if not isinstance(passphrase, str) or not passphrase:
            raise ValueError("passphrase must be a non-empty string")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
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
        """Encrypt and store a secret, preserving an existing ACL by default."""
        caller = self._validate_identity(caller, field="caller")
        acl = self._normalize_acl(acl)
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            existing = self._conn.execute(
                "SELECT acl FROM secrets WHERE name = ?", (name,)
            ).fetchone()
            if existing is not None:
                current_acl = [s for s in (existing["acl"] or "").split(",") if s]
                if current_acl and caller not in current_acl:
                    self._audit(caller, "set", name, False)
                    raise PermissionError(
                        f"Caller {caller!r} not permitted to modify {name!r}"
                    )
                acl_str = existing["acl"] if acl is None else ",".join(acl)
            else:
                acl_str = ",".join(acl) if acl else ""
            payload = value.encode() if isinstance(value, str) else value
            ciphertext = self._fernet.encrypt(payload)
            now = time.time()
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
    def get_bytes(self, name: str, *, caller: str = "library") -> bytes | None:
        """Decrypt and return raw secret bytes, or None if not found."""
        caller = self._validate_identity(caller, field="caller")
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            row = self._conn.execute(
                "SELECT ciphertext, acl FROM secrets WHERE name = ?", (name,)
            ).fetchone()
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
                plaintext = self._fernet.decrypt(row["ciphertext"])
            except InvalidToken:
                self._audit(caller, "get", name, False)
                raise
            self._audit(caller, "get", name, True)
            return plaintext

    def get(self, name: str, *, caller: str = "library") -> str | None:
        """Decrypt and UTF-8 decode a text secret, or None if not found."""
        value = self.get_bytes(name, caller=caller)
        return None if value is None else value.decode("utf-8")
    def delete(self, name: str, *, caller: str = "library") -> bool:
        """Delete an authorized secret. The store must be unlocked."""
        caller = self._validate_identity(caller, field="caller")
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            row = self._conn.execute(
                "SELECT acl FROM secrets WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                self._audit(caller, "delete", name, False)
                return False
            acl = [s for s in (row["acl"] or "").split(",") if s]
            if acl and caller not in acl:
                self._audit(caller, "delete", name, False)
                raise PermissionError(
                    f"Caller {caller!r} not permitted to delete {name!r}"
                )
            self._conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
            self._audit(caller, "delete", name, True)
            return True
    def set_many(
        self,
        values: dict[str, str | bytes],
        *,
        caller: str = "library",
        acl: list[str] | None = None,
    ) -> None:
        """Store multiple values in one SQLite transaction."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                for name, value in values.items():
                    self.set(name, value, caller=caller, acl=acl)
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    def get_many(
        self, names: list[str], *, caller: str = "library"
    ) -> dict[str, str | None]:
        """Retrieve multiple UTF-8 text secrets."""
        return {name: self.get(name, caller=caller) for name in names}
    def list_keys(
        self, *, caller: str = "library", acl_filter: bool = True
    ) -> list[SecretMetadata]:
        """List secret names with metadata. Respects ACL by default."""
        caller = self._validate_identity(caller, field="caller")
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
        """Re-encrypt all secrets atomically and publish the new key last."""
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            old_fernet = self._fernet
            if new_passphrase is None:
                new_key = Fernet.generate_key()
                new_salt = None
            else:
                new_salt = os.urandom(16)
                new_key = self._derive_key(new_passphrase, new_salt)
            new_fernet = Fernet(new_key)
            rows = self._conn.execute("SELECT name, ciphertext FROM secrets").fetchall()
            rewritten = [
                (new_fernet.encrypt(old_fernet.decrypt(r["ciphertext"])), r["name"])
                for r in rows
            ]
            check = new_fernet.encrypt(b"gunz-utils-secure-store-v1")
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                self._conn.executemany(
                    "UPDATE secrets SET ciphertext = ? WHERE name = ?", rewritten
                )
                self._conn.execute(
                    "INSERT OR REPLACE INTO store_meta(key, value) "
                    "VALUES ('key_check', ?)",
                    (check,),
                )
                if new_salt is None:
                    self._write_private(self._master_key_path, new_key)
                    if self._salt_path.exists():
                        self._salt_path.unlink()
                else:
                    self._write_private(self._salt_path, new_salt)
                    if self._master_key_path.exists():
                        self._master_key_path.unlink()
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._fernet = new_fernet
    def lock(self) -> None:
        """Atomically clear the Fernet instance. Thread-safe."""
        with self._fernet_lock:
            self._fernet = None

    def audit_events(self, *, limit: int = 100) -> list[dict[str, object]]:
        """Return the newest audit events without secret values."""
        if limit <= 0 or limit > 10_000:
            raise ValueError("limit must be in [1, 10000]")
        with self._lock:
            rows = self._conn.execute(
                "SELECT timestamp, caller, action, secret_name, allowed "
                "FROM audit ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def __enter__(self) -> SecureStore:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
    def close(self) -> None:
        with self._lock:
            self._conn.close()
            self._fernet = None


def main_unlock_interactive() -> SecureStore:
    """Convenience helper for CLI: prompts for passphrase if needed."""
    store = SecureStore()
    if store._salt_path.exists():
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
