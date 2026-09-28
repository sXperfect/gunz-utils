"""Hashing helpers for content addressing and file integrity."""

from __future__ import annotations

import hashlib
import pathlib
from typing import BinaryIO, cast

from ._version import __version__ as __version__

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = [
    "content_hash",
    "directory_hash",
    "directory_manifest",
    "file_hash",
    "short_hash",
    "structured_hash",
    "DEFAULT_ALGO",
    "DEFAULT_CHUNK_SIZE",
    "SUPPORTED_ALGOS",
]

DEFAULT_ALGO: str = "sha256"
# ? 64 KiB matches the canonical streaming-IO block size; large enough to amortize
# ? syscall overhead, small enough to bound memory for huge files.
DEFAULT_CHUNK_SIZE: int = 65536
# ? Curated subset keeps behavior predictable across systems; relying on
# ? hashlib.algorithms_available would expose platform-specific names (e.g.
# ? shake_128) that change between OpenSSL versions.
SUPPORTED_ALGOS: frozenset[str] = frozenset(
    {"sha256", "sha512", "sha1", "blake2b", "blake2s", "sha3_256", "md5"}
)
# MD5 and SHA-1 remain for compatibility and non-adversarial fingerprints only.
# Security-sensitive identity code such as ContentAddressedStore rejects them.
_MIN_SHORT_CHARS: int = 4
_MAX_SHORT_CHARS: int = 128


def content_hash(data: bytes | str, *, algo: str = DEFAULT_ALGO) -> str:
    """Compute the lowercase hex digest of ``data``.

    String inputs are UTF-8 encoded before hashing. Algorithm is validated
    against :data:`SUPPORTED_ALGOS` so behavior is identical across Python
    builds and OpenSSL versions.

    Parameters
    ----------
    data : bytes | str
        Bytes to hash, or a string (UTF-8 encoded before hashing).
    algo : str, optional
        Hash algorithm name. Must appear in :data:`SUPPORTED_ALGOS`.
        Default is ``"sha256"``.

    Returns
    -------
    str
        Lowercase hex digest.

    Raises
    ------
    TypeError
        If ``data`` is not ``bytes`` or ``str``.
    ValueError
        If ``algo`` is not in :data:`SUPPORTED_ALGOS`.

    Examples
    --------
    >>> content_hash(b"hello")
    '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    >>> content_hash("hello") == content_hash(b"hello")
    True
    """
    if type(data) not in (bytes, str):
        raise TypeError(f"data must be bytes or str, got {type(data).__name__}")
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(
            f"unsupported algo {algo!r}; expected one of {sorted(SUPPORTED_ALGOS)}"
        )
    # ? str -> bytes via UTF-8 encoding (single canonical form for hashing).
    payload = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.new(algo, payload).hexdigest()


def _hash_binary_handle(
    handle: BinaryIO,
    *,
    algo: str,
    chunk_size: int,
) -> str:
    hasher = hashlib.new(algo)
    while block := handle.read(chunk_size):
        hasher.update(block)
    return hasher.hexdigest()


def file_hash(
    path: str | pathlib.Path,
    *,
    algo: str = DEFAULT_ALGO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute the hex digest of a file's contents, streamed in chunks.

    Memory usage is bounded by ``chunk_size`` regardless of file size, so
    multi-GB inputs do not blow up RAM. The file is opened in binary mode.

    Parameters
    ----------
    path : str | pathlib.Path
        File to hash.
    algo : str, optional
        Hash algorithm name. Must appear in :data:`SUPPORTED_ALGOS`.
        Default is ``"sha256"``.
    chunk_size : int, optional
        Read block size in bytes. Must be positive. Default is
        :data:`DEFAULT_CHUNK_SIZE` (64 KiB).

    Returns
    -------
    str
        Lowercase hex digest of the file contents.

    Raises
    ------
    ValueError
        If ``algo`` is unsupported or ``chunk_size`` is not positive.
    FileNotFoundError
        If ``path`` does not exist.
    IsADirectoryError
        If ``path`` is a directory.
    """
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(
            f"unsupported algo {algo!r}; expected one of {sorted(SUPPORTED_ALGOS)}"
        )
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size <= 0
    ):
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")
    with open(path, "rb") as handle:
        return _hash_binary_handle(
            handle,
            algo=algo,
            chunk_size=chunk_size,
        )


def short_hash(data: bytes | str, *, chars: int = 8, algo: str = DEFAULT_ALGO) -> str:
    """Return the first ``chars`` hex characters of :func:`content_hash`.

    Useful for human-visible content fingerprints (logs, cache keys, git-style
    short SHAs). 8 chars (32 bits) is a reasonable default for non-cryptographic
    dedup; longer strings reduce collision probability.

    Parameters
    ----------
    data : bytes | str
        Bytes or string to hash (forwarded to :func:`content_hash`).
    chars : int, optional
        Length of the returned prefix. Must be in
        ``[_MIN_SHORT_CHARS, _MAX_SHORT_CHARS]``. Default is ``8``.
    algo : str, optional
        Hash algorithm name (forwarded to :func:`content_hash`).

    Returns
    -------
    str
        Lowercase hex prefix of length ``chars``.

    Raises
    ------
    ValueError
        If ``chars`` is out of range or ``algo`` is unsupported.
    TypeError
        If ``data`` is not ``bytes`` or ``str``.

    Examples
    --------
    >>> short_hash(b"hello")
    '2cf24dba'
    >>> short_hash(b"hello") == content_hash(b"hello")[:8]
    True
    """
    if (
        isinstance(chars, bool)
        or not isinstance(chars, int)
        or chars < _MIN_SHORT_CHARS
        or chars > _MAX_SHORT_CHARS
    ):
        raise ValueError(
            f"chars must be an integer in "
            f"[{_MIN_SHORT_CHARS}, {_MAX_SHORT_CHARS}], got {chars!r}"
        )
    return content_hash(data, algo=algo)[:chars]



def structured_hash(
    value: object,
    *,
    algo: str = DEFAULT_ALGO,
) -> str:
    """Hash structured Python data through canonical JSON serialization.

    Parameters
    ----------
    value : object
        Value supported by :func:`gunz_utils.serialization.canonical_json`.
    algo : str, optional
        Hash algorithm accepted by :func:`content_hash`.

    Returns
    -------
    str
        Stable hexadecimal digest.

    Notes
    -----
    Mapping key order and set iteration order do not affect the resulting
    digest because serialization is canonicalized first.
    """
    from .serialization import canonical_json

    return content_hash(
        canonical_json(value),
        algo=algo,
    )


def directory_manifest(
    root: str | pathlib.Path,
    *,
    algo: str = DEFAULT_ALGO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, str]:
    """Return stable relative-path hashes for every regular file below root.

    Parameters
    ----------
    root : str | pathlib.Path
        Directory to traverse recursively.
    algo : str, optional
        Hash algorithm used for each file.
    chunk_size : int, optional
        Streaming block size used by :func:`file_hash`.

    Returns
    -------
    dict[str, str]
        Relative POSIX paths mapped to file digests, ordered lexically by path.
        Symbolic links are excluded so the manifest cannot silently depend on
        content outside the requested root.

    Raises
    ------
    NotADirectoryError
        If root is not a directory.
    """
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(
            f"unsupported algo {algo!r}; expected one of {sorted(SUPPORTED_ALGOS)}"
        )
    if (
        isinstance(chunk_size, bool)
        or not isinstance(chunk_size, int)
        or chunk_size <= 0
    ):
        raise ValueError(
            f"chunk_size must be a positive integer, got {chunk_size!r}"
        )

    base = pathlib.Path(root).resolve()
    if not base.is_dir():
        raise NotADirectoryError(str(base))

    files = sorted(
        (
            path
            for path in base.rglob("*")
            if path.is_file() and not path.is_symlink()
        ),
        key=lambda path: path.relative_to(base).as_posix(),
    )
    from .security import open_path_under_base

    manifest: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(base).as_posix()
        try:
            # ? Security (VULN-2026-011): Handle open_path_under_base traversal errors
            # ? gracefully so directory symlinks resolving outside root do not cause unhandled crashes.
            with open_path_under_base(
                str(base),
                relative,
                mode="rb",
            ) as handle:
                manifest[relative] = _hash_binary_handle(
                    cast(BinaryIO, handle),
                    algo=algo,
                    chunk_size=chunk_size,
                )
        except ValueError:
            # Skip file if path traversal / symlink policy rejects opening under base
            continue
    return manifest


def directory_hash(
    root: str | pathlib.Path,
    *,
    algo: str = DEFAULT_ALGO,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Return one digest representing paths and contents below a directory.

    The digest changes when a relative path or any file content changes.
    """
    return structured_hash(
        directory_manifest(
            root,
            algo=algo,
            chunk_size=chunk_size,
        ),
        algo=algo,
    )
