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
        .lock               Inter-process coordination lock (mode 0600).

Two unlock modes::

    file (default):   reads master.key directly (server/headless).
    passphrase:       derives master.key from a user passphrase +
                      a salt (laptop / interactive).

Secrets are Fernet-encrypted (AES-128-CBC + HMAC-SHA256) at rest.
Each secret has an optional ACL list of caller IDs permitted to
read it (e.g. ``["mcp", "cli", "library"]``). Empty ACL = open access.

Threat-model boundaries and assumptions:
    - Caller identity (``caller`` parameter) is an application-level label,
      not an authenticated cryptographic principal. In single-process or
      untrusted caller environments, enforcement is cooperative.
    - File-key mode assumes the storage directory and filesystem are trusted
      up to OS user boundaries. Attackers with raw disk read access can
      read ``master.key``. Passphrase mode derives keys via PBKDF2 with 600,000
      iterations.
    - In-process memory: Fernet key material and decrypted secrets reside in
      process memory while unlocked. Memory scrubbing is bounded by Python's
      runtime string/bytes lifecycle.
    - Audit log entries record operations within SQLite but do not defend
      against malicious local database truncation or deletion if an attacker
      possesses write access to the SQLite file.
    - Inter-process write coordination is enforced via kernel file locks
      (``flock``) and transactional key-generation checks.

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

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
import base64
import json
import os
import re
import sqlite3
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .._version import __version__ as __version__

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

_PBKDF2_ITERATIONS = 600_000  #? OWASP 2023 recommendation for SHA-256
_KEY_FILE_MODE = 0o600  #? owner read/write only
_DIR_MODE = 0o700
_LIBRARY_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RECORD_ENVELOPE_MAGIC = b"\x00GZENV1\x00"
_RECORD_FORMAT_STRICT = b"envelope-v1"
_RECORD_FORMAT_LEGACY = b"legacy"
_KEY_CHECK_LEGACY = b"gunz-utils-secure-store-v1"
_KEY_CHECK_STRICT = b"gunz-utils-secure-store-v2:strict"
_KEY_CHECK_MIGRATION = b"gunz-utils-secure-store-v2:legacy"
_WINDOWS_LOCK_TIMEOUT = 60.0


def _lock_fd(
    fd: int,
) -> None:
    """Take an exclusive inter-process lock on ``fd`` (blocking).

    Parameters
    ----------
    fd : int
        fd parameter.
    """
    if sys.platform == "win32":
        deadline = time.monotonic() + _WINDOWS_LOCK_TIMEOUT
        while True:
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "timed out waiting for the secure-store lock"
                    ) from None
                time.sleep(0.05)
    else:
        fcntl.flock(fd, fcntl.LOCK_EX)


def _unlock_fd(
    fd: int,
) -> None:
    """Release the inter-process lock held on ``fd``.

    Parameters
    ----------
    fd : int
        fd parameter.
    """
    if sys.platform == "win32":
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _close_quietly(
    fd: int,
) -> None:
    """Close ``fd`` without masking an in-flight exception.

    Parameters
    ----------
    fd : int
        fd parameter.
    """
    try:
        os.close(fd)
    except OSError:
        pass


class _ReentrantFileLock:
    """Inter-process and inter-thread file lock protecting store mutations."""

    def __init__(self,
        lock_path: Path,
    ) -> None:
        self._path = lock_path
        self._thread_lock = threading.RLock()
        self._depth = 0
        self._fd: int = -1

    def acquire(self) -> None:
        """acquire() function.

        No parameters and no return value.
        """
        self._thread_lock.acquire()
        try:
            if self._depth == 0:
                flags = os.O_RDWR | os.O_CREAT
                if hasattr(os, "O_CLOEXEC"):
                    flags |= os.O_CLOEXEC
                if hasattr(os, "O_NOFOLLOW"):
                    flags |= os.O_NOFOLLOW
                fd = os.open(self._path, flags, _KEY_FILE_MODE)
                try:
                    if os.name == "posix":
                        os.fchmod(fd, _KEY_FILE_MODE)
                    _lock_fd(fd)
                except BaseException:
                    _close_quietly(fd)
                    raise
                self._fd = fd
            self._depth += 1
        except BaseException:
            self._thread_lock.release()
            raise

    def release(self) -> None:
        """release() function.

        No parameters and no return value.
        """
        if self._depth == 0:
            raise RuntimeError("Cannot release un-acquired file lock")
        try:
            self._depth -= 1
            if self._depth == 0:
                fd = self._fd
                self._fd = -1
                try:
                    _unlock_fd(fd)
                finally:
                    #? Closing the descriptor drops any remaining OS lock; a
                    #? close failure must not mask an unlock failure.
                    _close_quietly(fd)
        finally:
            self._thread_lock.release()

    def __enter__(self) -> _ReentrantFileLock:
        self.acquire()
        return self

    def __exit__(self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        self.release()


def _pack_envelope(
    name: str,
    acl_str: str,
    payload: bytes,
) -> bytes:
    """Wrap raw secret payload with authenticated record binding metadata.

    Parameters
    ----------
    name : str
        name parameter.
    acl_str : str
        acl_str parameter.
    payload : bytes
        payload parameter.

    Returns
    -------
    bytes
        The result of the operation.
    """
    envelope = {
        "name": name,
        "acl": acl_str,
        "payload": base64.b64encode(payload).decode("ascii"),
    }
    encoded = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return _RECORD_ENVELOPE_MAGIC + encoded


def _decode_record(
    raw: bytes,
    *,
    expected_name: str,
    expected_acl: str,
    allow_legacy: bool,
) -> tuple[bytes, bool]:
    """Decode a decrypted record, returning ``(payload, metadata_bound)``.

    Records are only trusted as metadata-bound when they carry a valid
    envelope whose name/ACL match the row. Legacy (pre-envelope) records are
    accepted, and reported as unbound, only while ``allow_legacy`` is true;
    once a store has been migrated, they are rejected. Decryption is already
    authenticated by Fernet, so a decrypted payload that only *resembles* an
    envelope (magic prefix, malformed body) can only be legacy data.
    """
    if not raw.startswith(_RECORD_ENVELOPE_MAGIC):
        if allow_legacy:
            return raw, False
        raise InvalidToken("unbound legacy record rejected")

    try:
        data = json.loads(raw[len(_RECORD_ENVELOPE_MAGIC) :].decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("invalid envelope structure")
        record_name = data.get("name")
        record_acl = data.get("acl")
        b64_payload = data.get("payload")
        if (
            not isinstance(record_name, str)
            or not isinstance(record_acl, str)
            or not isinstance(b64_payload, str)
        ):
            raise ValueError("malformed envelope fields")
        payload = base64.b64decode(b64_payload.encode("ascii"), validate=True)
    except ValueError as exc:  #? JSON, Unicode and base64 errors subclass it
        if allow_legacy:
            return raw, False
        raise InvalidToken("Malformed record envelope") from exc

    if record_name != expected_name or record_acl != expected_acl:
        raise InvalidToken("record envelope binding mismatch")
    return payload, True


def default_base_dir(
    library_name: str,
) -> Path:
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

    def __init__(self,
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
        self._pending_key_path = self._base_dir / ".master.key.pending"
        self._pending_salt_path = self._base_dir / ".master.salt.pending"
        self._db_path = self._base_dir / "config.db"
        self._prepare_private_database(self._db_path)
        self._lock_path = self._base_dir / ".lock"
        self._coordination_lock = _ReentrantFileLock(self._lock_path)
        self._lock = threading.RLock()
        self._fernet_lock = self._lock
        self._fernet: Fernet | None = None
        self._key_generation: int = 0
        self._passphrase_mode: bool = False
        self._conn = self._open_connection()
        self._init_schema()
        self._ensure_private_file(self._db_path)

    def _open_connection(self) -> sqlite3.Connection:
        """_open_connection() function.

        Returns
        -------
        sqlite3.Connection
            The result of the operation.
        """
        conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        #? Security (VULN-2026-006): bound SQLite lock waiting so concurrent
        #? processes cannot leave this connection waiting indefinitely.
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _reconnect_database(self) -> None:
        """Close and reconnect database if transaction state is corrupted.

        No parameters and no return value.
        """
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = self._open_connection()

    def _init_schema(self) -> None:
        """_init_schema() function.

        No parameters and no return value.
        """
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
        """is_unlocked() function.

        Returns
        -------
        bool
            The result of the operation.
        """
        with self._fernet_lock:
            return self._fernet is not None

    @property
    def fernet(self) -> Fernet | None:
        """Thread-safe Fernet accessor; returns the current instance or None.

        Returns
        -------
        Fernet | None
            The result of the operation.
        """
        with self._fernet_lock:
            return self._fernet

    @staticmethod
    def _ensure_private_directory(
        path: Path,
    ) -> None:
        """Create and verify an owner-private non-symlink directory.

        Parameters
        ----------
        path : Path
            path parameter.
        """
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
    def _ensure_private_file(
        path: Path,
    ) -> None:
        """Reject symlinks/non-files and enforce owner-only permissions.

        Parameters
        ----------
        path : Path
            path parameter.
        """
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
    def _prepare_private_database(cls,
        path: Path,
    ) -> None:
        """Create the SQLite file without a world-readable creation window.

        Parameters
        ----------
        path : Path
            path parameter.
        """
        if path.is_symlink():
            raise ValueError("secure-store database path must not be a symlink")
        if not path.exists():
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(path, flags, _KEY_FILE_MODE)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
        cls._ensure_private_file(path)

    @classmethod
    def _read_private(cls,
        path: Path,
    ) -> bytes:
        """Read key material through the descriptor that was type-checked.

        Parameters
        ----------
        path : Path
            path parameter.

        Returns
        -------
        bytes
            The result of the operation.
        """
        if path.is_symlink():
            raise ValueError(f"private path must not be a symlink: {path.name}")
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f"private path must be a regular file: {path.name}")
            if os.name == "posix":
                if info.st_uid != os.getuid():
                    raise PermissionError(f"private file has wrong owner: {path.name}")
                os.fchmod(descriptor, _KEY_FILE_MODE)
            with os.fdopen(descriptor, "rb") as handle:
                descriptor = -1
                return handle.read()
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _validate_secret_name(
        value: str,
    ) -> str:
        """_validate_secret_name() function.

        Parameters
        ----------
        value : str
            value parameter.

        Returns
        -------
        str
            The result of the operation.
        """
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 512
            or "\x00" in value
            or any(ord(character) < 0x20 for character in value)
        ):
            raise ValueError(
                "secret name must be a non-empty bounded string "
                "without control characters"
            )
        return value

    @staticmethod
    def _validate_identity(
        value: str,
        *,
        field: str,
    ) -> str:
        """_validate_identity() function.

        Parameters
        ----------
        value : str
            value parameter.
        field : str
            field parameter.

        Returns
        -------
        str
            The result of the operation.
        """
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 256
            or "," in value
            or "\x00" in value
        ):
            raise ValueError(
                f"{field} must be a non-empty identifier without commas or NULs"
            )
        return value

    @classmethod
    def _normalize_acl(cls,
        acl: list[str] | None,
    ) -> list[str] | None:
        """_normalize_acl() function.

        Parameters
        ----------
        acl : list[str] | None
            acl parameter.

        Returns
        -------
        list[str] | None
            The result of the operation.
        """
        if acl is None:
            return None
        if not isinstance(acl, list):
            raise ValueError("acl must be a list of caller names or None")
        normalized: list[str] = []
        seen: set[str] = set()
        for caller in acl:
            value = cls._validate_identity(caller, field="ACL entry caller")
            if value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized

    @staticmethod
    def _write_private(
        path: Path,
        data: bytes,
    ) -> None:
        """Create or replace a private file without a world-readable window.

        Parameters
        ----------
        path : Path
            path parameter.
        data : bytes
            data parameter.
        """
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            if os.name == "posix":
                os.fchmod(descriptor, _KEY_FILE_MODE)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = -1
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            if hasattr(os, "O_DIRECTORY"):
                directory_fd = os.open(
                    path.parent,
                    os.O_RDONLY | os.O_DIRECTORY,
                )
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _cleanup_pending_key_material(self) -> None:
        """_cleanup_pending_key_material() function.

        No parameters and no return value.
        """
        self._pending_key_path.unlink(missing_ok=True)
        self._pending_salt_path.unlink(missing_ok=True)

    def _fsync_base_dir(self) -> None:
        """_fsync_base_dir() function.

        No parameters and no return value.
        """
        if not hasattr(os, "O_DIRECTORY"):
            return
        descriptor = os.open(
            self._base_dir,
            os.O_RDONLY | os.O_DIRECTORY,
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _promote_pending_key_material(self,
        *,
        passphrase_mode: bool,
    ) -> None:
        """_promote_pending_key_material() function.

        Parameters
        ----------
        passphrase_mode : bool
            passphrase_mode parameter.
        """
        if passphrase_mode:
            os.replace(self._pending_salt_path, self._salt_path)
            self._master_key_path.unlink(missing_ok=True)
            self._pending_key_path.unlink(missing_ok=True)
        else:
            os.replace(self._pending_key_path, self._master_key_path)
            self._salt_path.unlink(missing_ok=True)
            self._pending_salt_path.unlink(missing_ok=True)
        self._fsync_base_dir()

    def _read_record_policy(self,
        fernet: Fernet,
    ) -> bool:
        """Verify authenticated policy and its persisted format marker.

        Parameters
        ----------
        fernet : Fernet
            fernet parameter.

        Returns
        -------
        bool
            The result of the operation.
        """
        check = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = 'key_check'"
        ).fetchone()
        if check is None:
            raise InvalidToken("Key check marker invalid or missing")
        policy = fernet.decrypt(check["value"])
        formats = {
            _KEY_CHECK_STRICT: _RECORD_FORMAT_STRICT,
            _KEY_CHECK_MIGRATION: _RECORD_FORMAT_LEGACY,
        }
        expected = formats.get(policy)
        if expected is None:
            raise InvalidToken("Authenticated record policy is missing or invalid")
        row = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = 'record_format'"
        ).fetchone()
        if row is None or row["value"] != expected:
            raise InvalidToken(
                "Record format marker does not match authenticated policy"
            )
        return policy == _KEY_CHECK_STRICT

    def _write_record_policy(self,
        fernet: Fernet,
        *,
        strict: bool,
    ) -> None:
        """Write policy and authenticated check within the caller's transaction.

        Parameters
        ----------
        fernet : Fernet
            fernet parameter.
        strict : bool
            strict parameter.
        """
        self._conn.execute(
            "INSERT OR REPLACE INTO store_meta(key, value) VALUES ('key_check', ?)",
            (fernet.encrypt(_KEY_CHECK_STRICT if strict else _KEY_CHECK_MIGRATION),),
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO store_meta(key, value) VALUES ('record_format', ?)",
            (_RECORD_FORMAT_STRICT if strict else _RECORD_FORMAT_LEGACY,),
        )

    def _verify_or_initialize_key(self,
        fernet: Fernet,
        *,
        allow_legacy: bool = False,
    ) -> None:
        """Verify key/policy or explicitly upgrade legacy metadata under both locks.

        Parameters
        ----------
        fernet : Fernet
            fernet parameter.
        allow_legacy : bool
            allow_legacy parameter.
        """
        row = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = 'key_check'"
        ).fetchone()
        policy = fernet.decrypt(row["value"]) if row is not None else None
        if policy in (_KEY_CHECK_STRICT, _KEY_CHECK_MIGRATION):
            self._read_record_policy(fernet)
            generation = self._read_generation()
            if generation is None:  #? Kept explicit for the optional return annotation.
                raise RuntimeError("Store generation metadata is missing")
            self._key_generation = generation
            return
        if policy not in (None, _KEY_CHECK_LEGACY):
            raise InvalidToken("Key check marker invalid")

        format_row = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = 'record_format'"
        ).fetchone()
        secret = self._conn.execute("SELECT ciphertext FROM secrets LIMIT 1").fetchone()
        strict = format_row is not None and format_row["value"] == _RECORD_FORMAT_STRICT
        if not strict and secret is not None and not allow_legacy:
            raise InvalidToken(
                "Legacy metadata requires explicit trusted unlock(allow_legacy=True)"
            )
        if format_row is not None and not strict:
            raise InvalidToken("Legacy record format metadata is invalid")
        if secret is not None:
            fernet.decrypt(secret["ciphertext"])
        generation = self._read_generation(missing_ok=True)
        if generation is None:
            generation = 1
        #? Seal the upgrade atomically: an interrupted unlock must not publish
        #? an authenticated policy without its corresponding format/generation.
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._write_record_policy(fernet, strict=strict or secret is None)
            self._conn.execute(
                "INSERT OR REPLACE INTO store_meta(key, value) "
                "VALUES ('key_generation', ?)",
                (str(generation).encode("ascii"),),
            )
            self._conn.execute("COMMIT")
        except BaseException as failure:
            try:
                self._reconnect_database()
            except BaseException:
                failure.add_note("Legacy policy upgrade connection recovery failed.")
            raise
        self._key_generation = generation

    def _read_generation(self,
        *,
        missing_ok: bool = False,
    ) -> int | None:
        """Return the persisted key generation, rejecting malformed metadata.

        Parameters
        ----------
        missing_ok : bool
            missing_ok parameter.

        Returns
        -------
        int | None
            The result of the operation.
        """
        row = self._conn.execute(
            "SELECT value FROM store_meta WHERE key = 'key_generation'"
        ).fetchone()
        if row is None:
            if missing_ok:
                return None
            raise RuntimeError(
                "Store generation metadata is missing; refusing to continue"
            )
        raw = row["value"]
        if (
            not isinstance(raw, bytes)
            or not raw.isdigit()
            or not raw.isascii()
            or int(raw) < 1
        ):
            raise RuntimeError(
                "Store generation metadata is invalid; refusing to continue"
            )
        return int(raw)

    def _verify_key_generation(self) -> None:
        """Verify this store instance's key matches current database key generation.

        No parameters and no return value.
        """
        if self._read_generation() != self._key_generation:
            raise RuntimeError(
                "Store key is stale; master key was rotated. Call unlock() again."
            )

    def _records_strict(self) -> bool:
        """Require a valid authenticated strict or trusted migration policy.

        Returns
        -------
        bool
            The result of the operation.
        """
        if self._fernet is None:
            raise RuntimeError("Store is locked. Call unlock() first.")
        return self._read_record_policy(self._fernet)

    def unlock(self,
        passphrase: str | None = None,
        *,
        allow_legacy: bool = False,
    ) -> None:
        """Unlock the store, recovering interrupted key publication if needed.

        ``allow_legacy=True`` explicitly trusts a pre-policy database for an
        initial upgrade. Use it only for trusted legacy input, then call
        :meth:`migrate_records`. It never bypasses a damaged modern policy.
        Whole-database authenticated snapshot rollback needs external freshness
        state and is outside this store's contract.

        Candidate verification and recovery run under the inter-process lock.
        """
        if not isinstance(allow_legacy, bool):
            raise ValueError("allow_legacy must be bool")
        if passphrase is not None and (
            not isinstance(passphrase, str) or not passphrase
        ):
            raise ValueError("passphrase must be a non-empty string")

        with self._lock, self._coordination_lock:
            candidates: list[tuple[Fernet, bool]] = []
            if passphrase is None:
                key_paths = (
                    self._master_key_path,
                    self._pending_key_path,
                )
                existing = [path for path in key_paths if path.exists()]
                if not existing:
                    if self._salt_path.exists() or self._pending_salt_path.exists():
                        raise RuntimeError(
                            "Store is passphrase-protected; passphrase required"
                        )
                    key = Fernet.generate_key()
                    self._write_private(self._master_key_path, key)
                    existing = [self._master_key_path]

                for path in existing:
                    key = self._read_private(path).strip()
                    candidates.append(
                        (
                            Fernet(key),
                            path == self._pending_key_path,
                        )
                    )
            else:
                salt_paths = (
                    self._salt_path,
                    self._pending_salt_path,
                )
                existing = [path for path in salt_paths if path.exists()]
                if not existing:
                    if (
                        self._master_key_path.exists()
                        or self._pending_key_path.exists()
                    ):
                        raise RuntimeError(
                            "Store uses file-key mode; do not supply passphrase"
                        )
                    salt = os.urandom(16)
                    self._write_private(self._salt_path, salt)
                    existing = [self._salt_path]

                for path in existing:
                    salt = self._read_private(path)
                    candidates.append(
                        (
                            Fernet(self._derive_key(passphrase, salt)),
                            path == self._pending_salt_path,
                        )
                    )

            last_error: InvalidToken | None = None
            for candidate, pending in candidates:
                try:
                    self._verify_or_initialize_key(candidate, allow_legacy=allow_legacy)
                except InvalidToken as exc:
                    last_error = exc
                    continue

                self._fernet = candidate
                self._passphrase_mode = passphrase is not None
                if pending:
                    self._promote_pending_key_material(
                        passphrase_mode=passphrase is not None,
                    )
                else:
                    self._cleanup_pending_key_material()
                return

            if last_error is not None:
                raise last_error
            raise InvalidToken

    @staticmethod
    def _derive_key(
        passphrase: str,
        salt: bytes,
    ) -> bytes:
        """_derive_key() function.

        Parameters
        ----------
        passphrase : str
            passphrase parameter.
        salt : bytes
            salt parameter.

        Returns
        -------
        bytes
            The result of the operation.
        """
        if not isinstance(passphrase, str) or not passphrase:
            raise ValueError("passphrase must be a non-empty string")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_PBKDF2_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

    def _audit(self,
        caller: str,
        action: str,
        secret_name: str | None,
        allowed: bool,
    ) -> None:
        """_audit() function.

        Parameters
        ----------
        caller : str
            caller parameter.
        action : str
            action parameter.
        secret_name : str | None
            secret_name parameter.
        allowed : bool
            allowed parameter.
        """
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO audit (timestamp, caller, action, secret_name, allowed)
                VALUES (?, ?, ?, ?, ?)
                """,
                (time.time(), caller, action, secret_name, 1 if allowed else 0),
            )

    @contextmanager
    def _transaction_locked(self) -> Iterator[None]:
        """Join an active transaction or own one for this mutation.

        Returns
        -------
        Iterator[None]
            The result of the operation.
        """
        with self._coordination_lock:
            self._verify_key_generation()
            started = not self._conn.in_transaction
            if started:
                self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
            except BaseException:
                if started and self._conn.in_transaction:
                    try:
                        self._conn.execute("ROLLBACK")
                    except Exception:
                        self._reconnect_database()
                raise
            else:
                if started:
                    try:
                        self._conn.execute("COMMIT")
                    except BaseException:
                        try:
                            if self._conn.in_transaction:
                                self._conn.execute("ROLLBACK")
                        except Exception:
                            pass
                        if self._conn.in_transaction:
                            self._reconnect_database()
                        raise

    def set(self,
        name: str,
        value: str | bytes,
        *,
        caller: str = "library",
        acl: list[str] | None = None,
    ) -> None:
        """Encrypt and store a secret, preserving an existing ACL by default.

        Parameters
        ----------
        name : str
            name parameter.
        value : str | bytes
            value parameter.
        caller : str
            caller parameter.
        acl : list[str] | None
            acl parameter.
        """
        name = self._validate_secret_name(name)
        caller = self._validate_identity(caller, field="caller")
        acl = self._normalize_acl(acl)
        if not isinstance(value, (str, bytes)):
            raise TypeError("value must be str or bytes")

        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            try:
                with self._transaction_locked():
                    existing = self._conn.execute(
                        "SELECT ciphertext, acl FROM secrets WHERE name = ?",
                        (name,),
                    ).fetchone()
                    if existing is not None:
                        stored_acl_str = existing["acl"] or ""
                        try:
                            raw_payload = self._fernet.decrypt(existing["ciphertext"])
                            allow_legacy = not self._records_strict()
                            _decode_record(
                                raw_payload,
                                expected_name=name,
                                expected_acl=stored_acl_str,
                                allow_legacy=allow_legacy,
                            )
                        except InvalidToken as exc:
                            raise InvalidToken(
                                f"Cannot overwrite {name!r}: existing record "
                                "envelope integrity check failed"
                            ) from exc

                        current_acl = [
                            item for item in stored_acl_str.split(",") if item
                        ]
                        if current_acl and caller not in current_acl:
                            raise PermissionError(
                                f"Caller {caller!r} not permitted to modify "
                                f"{name!r}"
                            )
                        acl_str = stored_acl_str if acl is None else ",".join(acl)
                    else:
                        acl_str = ",".join(acl) if acl else ""

                    payload = value.encode() if isinstance(value, str) else value
                    enveloped = _pack_envelope(name, acl_str, payload)
                    ciphertext = self._fernet.encrypt(enveloped)
                    now = time.time()
                    self._conn.execute(
                        """
                        INSERT INTO secrets (
                            name, ciphertext, acl, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(name) DO UPDATE SET
                            ciphertext = excluded.ciphertext,
                            acl = excluded.acl,
                            updated_at = excluded.updated_at
                        """,
                        (name, ciphertext, acl_str, now, now),
                    )
                    self._audit(caller, "set", name, True)
            except (PermissionError, InvalidToken):
                if not self._conn.in_transaction:
                    self._audit(caller, "set", name, False)
                raise

    def get_bytes(self,
        name: str,
        *,
        caller: str = "library",
    ) -> bytes | None:
        """Decrypt and return raw secret bytes, or None if not found.

        Parameters
        ----------
        name : str
            name parameter.
        caller : str
            caller parameter.

        Returns
        -------
        bytes | None
            The result of the operation.
        """
        name = self._validate_secret_name(name)
        caller = self._validate_identity(caller, field="caller")
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            self._verify_key_generation()
            row = self._conn.execute(
                "SELECT ciphertext, acl FROM secrets WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                self._audit(caller, "get", name, False)
                return None
            acl_str = row["acl"] or ""
            acl = [s for s in acl_str.split(",") if s]
            if acl and caller not in acl:
                self._audit(caller, "get", name, False)
                raise PermissionError(
                    f"Caller {caller!r} not in ACL {acl} for secret {name!r}"
                )
            try:
                raw_payload = self._fernet.decrypt(row["ciphertext"])
                allow_legacy = not self._records_strict()
                plaintext, _ = _decode_record(
                    raw_payload,
                    expected_name=name,
                    expected_acl=acl_str,
                    allow_legacy=allow_legacy,
                )
            except InvalidToken:
                self._audit(caller, "get", name, False)
                raise
            self._audit(caller, "get", name, True)
            return plaintext

    def get(self,
        name: str,
        *,
        caller: str = "library",
    ) -> str | None:
        """Decrypt and UTF-8 decode a text secret, or None if not found.

        Parameters
        ----------
        name : str
            name parameter.
        caller : str
            caller parameter.

        Returns
        -------
        str | None
            The result of the operation.
        """
        value = self.get_bytes(name, caller=caller)
        return None if value is None else value.decode("utf-8")

    def delete(self,
        name: str,
        *,
        caller: str = "library",
    ) -> bool:
        """Delete an authorized secret. The store must be unlocked.

        Parameters
        ----------
        name : str
            name parameter.
        caller : str
            caller parameter.

        Returns
        -------
        bool
            The result of the operation.
        """
        name = self._validate_secret_name(name)
        caller = self._validate_identity(caller, field="caller")
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            try:
                with self._transaction_locked():
                    row = self._conn.execute(
                        "SELECT ciphertext, acl FROM secrets WHERE name = ?",
                        (name,),
                    ).fetchone()
                    if row is None:
                        self._audit(caller, "delete", name, False)
                        return False

                    stored_acl_str = row["acl"] or ""
                    try:
                        raw_payload = self._fernet.decrypt(row["ciphertext"])
                        allow_legacy = not self._records_strict()
                        _decode_record(
                            raw_payload,
                            expected_name=name,
                            expected_acl=stored_acl_str,
                            allow_legacy=allow_legacy,
                        )
                    except InvalidToken as exc:
                        raise InvalidToken(
                            f"Cannot delete {name!r}: existing record "
                            "envelope integrity check failed"
                        ) from exc

                    acl = [item for item in stored_acl_str.split(",") if item]
                    if acl and caller not in acl:
                        raise PermissionError(
                            f"Caller {caller!r} not permitted to delete " f"{name!r}"
                        )

                    self._conn.execute(
                        "DELETE FROM secrets WHERE name = ?",
                        (name,),
                    )
                    self._audit(caller, "delete", name, True)
                    return True
            except (PermissionError, InvalidToken):
                if not self._conn.in_transaction:
                    self._audit(caller, "delete", name, False)
                raise

    def set_many(self,
        values: dict[str, str | bytes],
        *,
        caller: str = "library",
        acl: list[str] | None = None,
    ) -> None:
        """Store multiple values and their audit events in one transaction.

        Parameters
        ----------
        values : dict[str, str | bytes]
            values parameter.
        caller : str
            caller parameter.
        acl : list[str] | None
            acl parameter.
        """
        if not isinstance(values, dict):
            raise ValueError("values must be a dict")
        caller = self._validate_identity(caller, field="caller")
        acl = self._normalize_acl(acl)

        normalized: list[tuple[str, str | bytes]] = []
        for name, value in values.items():
            normalized_name = self._validate_secret_name(name)
            if not isinstance(value, (str, bytes)):
                raise TypeError("value must be str or bytes")
            normalized.append((normalized_name, value))

        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            try:
                with self._transaction_locked():
                    for name, value in normalized:
                        self.set(
                            name,
                            value,
                            caller=caller,
                            acl=acl,
                        )
                    self._audit(caller, "set_many", None, True)
            except BaseException:
                if not self._conn.in_transaction:
                    try:
                        self._audit(caller, "set_many", None, False)
                    except sqlite3.Error:
                        pass
                raise

    def get_many(self,
        names: list[str],
        *,
        caller: str = "library",
    ) -> dict[str, str | None]:
        """Retrieve multiple UTF-8 text secrets.

        Parameters
        ----------
        names : list[str]
            names parameter.
        caller : str
            caller parameter.

        Returns
        -------
        dict[str, str | None]
            The result of the operation.
        """
        if not isinstance(names, list):
            raise ValueError("names must be a list")
        caller = self._validate_identity(caller, field="caller")
        validated = [self._validate_secret_name(name) for name in names]
        return {name: self.get(name, caller=caller) for name in validated}

    def list_keys(self,
        *,
        caller: str = "library",
        acl_filter: bool = True,
    ) -> list[SecretMetadata]:
        """List secret names with metadata. Respects ACL by default.

        Parameters
        ----------
        caller : str
            caller parameter.
        acl_filter : bool
            acl_filter parameter.

        Returns
        -------
        list[SecretMetadata]
            The result of the operation.
        """
        caller = self._validate_identity(caller, field="caller")
        if not isinstance(acl_filter, bool):
            raise ValueError("acl_filter must be bool")
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

    def rotate_master_key(self,
        new_passphrase: str | None = None,
        *,
        allow_mode_switch: bool = False,
    ) -> None:
        """Re-encrypt secrets with crash-recoverable key publication.

        Parameters
        ----------
        new_passphrase : str | None
            New master passphrase if using passphrase mode, or None for file-key mode.
        allow_mode_switch : bool
            Must be explicitly set to True when transitioning between file-key mode
            and passphrase mode, preventing accidental protection-mode downgrades.
        """
        if new_passphrase is not None and (
            not isinstance(new_passphrase, str) or not new_passphrase
        ):
            raise ValueError("new_passphrase must be a non-empty string or None")
        if not isinstance(allow_mode_switch, bool):
            raise ValueError("allow_mode_switch must be a bool")

        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")

            current_is_passphrase = (
                self._salt_path.exists()
                or self._pending_salt_path.exists()
                or self._passphrase_mode
            )
            target_is_passphrase = new_passphrase is not None

            if (
                current_is_passphrase
                and not target_is_passphrase
                and not allow_mode_switch
            ):
                raise ValueError(
                    "Cannot downgrade passphrase-protected store to file-key mode "
                    "without allow_mode_switch=True"
                )
            if (
                not current_is_passphrase
                and target_is_passphrase
                and not allow_mode_switch
            ):
                raise ValueError(
                    "Cannot convert file-key store to passphrase-protected mode "
                    "without allow_mode_switch=True"
                )

            with self._coordination_lock:
                self._verify_key_generation()
                self._records_strict()
                if self._pending_key_path.exists() or self._pending_salt_path.exists():
                    #? A prior rotation may have committed without publishing.
                    #? Preserve its only durable key before staging another one.
                    self._promote_pending_key_material(
                        passphrase_mode=self._passphrase_mode,
                    )
                self._cleanup_pending_key_material()
                old_fernet = self._fernet
                if new_passphrase is None:
                    new_key = Fernet.generate_key()
                    self._write_private(self._pending_key_path, new_key)
                else:
                    new_salt = os.urandom(16)
                    new_key = self._derive_key(new_passphrase, new_salt)
                    self._write_private(self._pending_salt_path, new_salt)

                new_fernet = Fernet(new_key)
                old_generation = self._key_generation
                new_gen = old_generation + 1

                try:
                    self._conn.execute("BEGIN IMMEDIATE")
                    self._verify_key_generation()
                    rows = self._conn.execute(
                        "SELECT name, ciphertext, acl FROM secrets"
                    ).fetchall()

                    allow_legacy = not self._records_strict()
                    rewritten: list[tuple[bytes, str]] = []
                    for row in rows:
                        name = row["name"]
                        acl_str = row["acl"] or ""
                        raw_payload = old_fernet.decrypt(row["ciphertext"])
                        plaintext, _ = _decode_record(
                            raw_payload,
                            expected_name=name,
                            expected_acl=acl_str,
                            allow_legacy=allow_legacy,
                        )
                        new_enveloped = _pack_envelope(name, acl_str, plaintext)
                        rewritten.append((new_fernet.encrypt(new_enveloped), name))

                    new_gen_bytes = str(new_gen).encode("ascii")

                    self._conn.executemany(
                        "UPDATE secrets SET ciphertext = ? WHERE name = ?",
                        rewritten,
                    )
                    self._conn.execute(
                        "INSERT OR REPLACE INTO store_meta(key, value) "
                        "VALUES ('key_generation', ?)",
                        (new_gen_bytes,),
                    )
                    self._write_record_policy(new_fernet, strict=True)
                    self._conn.execute("COMMIT")
                except BaseException as failure:
                    self._recover_failed_rotation(
                        failure,
                        old_fernet=old_fernet,
                        new_fernet=new_fernet,
                        old_generation=old_generation,
                        new_generation=new_gen,
                        passphrase_mode=target_is_passphrase,
                    )
                    raise

                self._fernet = new_fernet
                self._key_generation = new_gen
                self._passphrase_mode = target_is_passphrase
                self._promote_pending_key_material(
                    passphrase_mode=target_is_passphrase,
                )

    def _recover_failed_rotation(self,
        failure: BaseException,
        *,
        old_fernet: Fernet,
        new_fernet: Fernet,
        old_generation: int,
        new_generation: int,
        passphrase_mode: bool,
    ) -> None:
        """Reconcile durable state without losing the original rotation failure.

        Parameters
        ----------
        failure : BaseException
            failure parameter.
        old_fernet : Fernet
            old_fernet parameter.
        new_fernet : Fernet
            new_fernet parameter.
        old_generation : int
            old_generation parameter.
        new_generation : int
            new_generation parameter.
        passphrase_mode : bool
            passphrase_mode parameter.
        """
        try:
            if self._conn.in_transaction:
                try:
                    self._conn.execute("ROLLBACK")
                except BaseException:
                    #? Closing the connection drops an uncommitted transaction.
                    #? COMMIT may also have succeeded before its wrapper failed.
                    pass
            self._reconnect_database()
            generation = self._read_generation()
            if generation == old_generation:
                self._read_record_policy(old_fernet)
                self._fernet = old_fernet
                self._key_generation = old_generation
                self._cleanup_pending_key_material()
            elif generation == new_generation:
                self._read_record_policy(new_fernet)
                self._fernet = new_fernet
                self._key_generation = new_generation
                self._passphrase_mode = passphrase_mode
                #? Keep pending material: the database is committed but key
                #? publication still needs recovery by coordinated unlock.
            else:
                raise RuntimeError("Unexpected durable key generation")
        except BaseException:
            self._fernet = None
            failure.add_note(
                "Rotation recovery could not verify durable state; store locked "
                "and pending key material retained for recovery."
            )

    def migrate_records(self) -> int:
        """Migrate any legacy un-enveloped secrets to authenticated envelopes.

        Returns the number of migrated records. Once migrated, the store
        permanently enforces metadata binding on all future reads.
        """
        with self._lock, self._coordination_lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            self._verify_key_generation()

            rows = self._conn.execute(
                "SELECT name, ciphertext, acl FROM secrets"
            ).fetchall()

            allow_legacy = not self._records_strict()
            rewritten: list[tuple[bytes, str]] = []
            migrated_count = 0

            for row in rows:
                name = row["name"]
                acl_str = row["acl"] or ""
                raw_payload = self._fernet.decrypt(row["ciphertext"])
                plaintext, is_bound = _decode_record(
                    raw_payload,
                    expected_name=name,
                    expected_acl=acl_str,
                    allow_legacy=allow_legacy,
                )
                if not is_bound:
                    new_enveloped = _pack_envelope(name, acl_str, plaintext)
                    rewritten.append((self._fernet.encrypt(new_enveloped), name))
                    migrated_count += 1

            with self._transaction_locked():
                if rewritten:
                    self._conn.executemany(
                        "UPDATE secrets SET ciphertext = ? WHERE name = ?",
                        rewritten,
                    )
                self._write_record_policy(self._fernet, strict=True)
            return migrated_count

    def verify_integrity(self) -> bool:
        """Verify the store key and secret record envelope bindings.

        Returns True if all record envelopes and the key-check marker are intact.
        Raises InvalidToken if tampering or key mismatch is detected.
        """
        with self._lock:
            if self._fernet is None:
                raise RuntimeError("Store is locked. Call unlock() first.")
            self._verify_key_generation()
            self._read_record_policy(self._fernet)

            rows = self._conn.execute(
                "SELECT name, ciphertext, acl FROM secrets"
            ).fetchall()
            allow_legacy = not self._records_strict()
            for r in rows:
                name = r["name"]
                acl_str = r["acl"] or ""
                raw_payload = self._fernet.decrypt(r["ciphertext"])
                _decode_record(
                    raw_payload,
                    expected_name=name,
                    expected_acl=acl_str,
                    allow_legacy=allow_legacy,
                )
            return True

    def lock(self) -> None:
        """Atomically clear the Fernet instance. Thread-safe.

        No parameters and no return value.
        """
        with self._fernet_lock:
            self._fernet = None

    def audit_events(self,
        *,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Return the newest audit events without secret values.

        Parameters
        ----------
        limit : int
            limit parameter.

        Returns
        -------
        list[dict[str, object]]
            The result of the operation.
        """
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or limit <= 0
            or limit > 10_000
        ):
            raise ValueError("limit must be an integer in [1, 10000]")
        with self._lock:
            rows = self._conn.execute(
                "SELECT timestamp, caller, action, secret_name, allowed "
                "FROM audit ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def __enter__(self) -> SecureStore:
        return self

    def __exit__(self,
        exc_type: object,
        exc: object,
        tb: object,
    ) -> None:
        self.close()

    def close(self) -> None:
        """close() function.

        No parameters and no return value.
        """
        with self._lock:
            self._conn.close()
            self._fernet = None


def main_unlock_interactive() -> SecureStore:
    """Convenience helper for CLI: prompts for passphrase if needed.

    Returns
    -------
    SecureStore
        The result of the operation.
    """
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
