"""Hashing helpers for content addressing and file integrity."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import hashlib
import hmac
import os
import pathlib
import stat
from collections.abc import Iterable
from typing import Any, BinaryIO, cast

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from . import security
from ._version import __version__ as __version__
from .serialization import canonical_json

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = [
    "DEFAULT_ALGO",
    "DEFAULT_CHUNK_SIZE",
    "MerkleTree",
    "RollingHash",
    "SUPPORTED_ALGOS",
    "compute_file_checksum",
    "content_hash",
    "directory_hash",
    "directory_manifest",
    "file_hash",
    "fnv1a_32",
    "fnv1a_64",
    "hmac_digest",
    "hmac_sha256",
    "murmurhash3_32",
    "rabin_karp_hash",
    "sha256_digest",
    "short_hash",
    "structured_hash",
    "verify_file_checksum",
    "verify_hmac",
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
#? MD5 and SHA-1 remain for compatibility and non-adversarial fingerprints only.
#? Security-sensitive identity code such as ContentAddressedStore rejects them.
_MIN_SHORT_CHARS: int = 4
_MAX_SHORT_CHARS: int = 128


def content_hash(
    data: bytes | bytearray | memoryview | str,
    *,
    algo: str = DEFAULT_ALGO,
) -> str:
    """Compute the lowercase hex digest of ``data``.

    String inputs are UTF-8 encoded before hashing. Algorithm is validated
    against :data:`SUPPORTED_ALGOS` so behavior is identical across Python
    builds and OpenSSL versions.

    Parameters
    ----------
    data : bytes | bytearray | memoryview | str
        Bytes or bytes-like object to hash, or a string (UTF-8 encoded).
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
        If ``data`` is not bytes-like or ``str``.
    ValueError
        If ``algo`` is not in :data:`SUPPORTED_ALGOS`.
    """
    if not isinstance(data, (bytes, bytearray, memoryview, str)):
        raise TypeError(f"data must be bytes-like or str, got {type(data).__name__}")
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(
            f"unsupported algo {algo!r}; expected one of {sorted(SUPPORTED_ALGOS)}"
        )
    if isinstance(data, str):
        payload: bytes | memoryview = data.encode("utf-8")
    elif isinstance(data, memoryview):
        payload = data.cast("B")
    elif isinstance(data, bytearray):
        payload = memoryview(data)
    else:
        payload = data
    return hashlib.new(algo, payload).hexdigest()


def _hash_binary_handle(
    handle: BinaryIO,
    *,
    algo: str,
    chunk_size: int,
) -> str:
    """_hash_binary_handle() function.

    Parameters
    ----------
    handle : BinaryIO
        handle parameter.
    algo : str
        algo parameter.
    chunk_size : int
        chunk_size parameter.

    Returns
    -------
    str
        The result of the operation.
    """
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
    flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(path, flags)
    try:
        mode = os.fstat(fd).st_mode
        if stat.S_ISDIR(mode):
            raise IsADirectoryError(f"path {path!r} is a directory")
        if not stat.S_ISREG(mode):
            raise ValueError(
                f"path {path!r} must be a regular file, not a FIFO, pipe, or device"
            )
        with os.fdopen(fd, "rb") as handle:
            fd = -1
            return _hash_binary_handle(
                handle,
                algo=algo,
                chunk_size=chunk_size,
            )
    finally:
        if fd >= 0:
            os.close(fd)


def short_hash(
    data: bytes | bytearray | memoryview | str,
    *,
    chars: int = 8,
    algo: str = DEFAULT_ALGO,
) -> str:
    """Return the first ``chars`` hex characters of :func:`content_hash`.

    Useful for human-visible content fingerprints (logs, cache keys, git-style
    short SHAs). 8 chars (32 bits) is a reasonable default for non-cryptographic
    dedup; longer strings reduce collision probability.

    Parameters
    ----------
    data : bytes | bytearray | memoryview | str
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
        If ``data`` is not bytes-like or ``str``.

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


def hmac_digest(
    key: bytes | bytearray | memoryview | str,
    data: bytes | bytearray | memoryview | str,
    *,
    algo: str = DEFAULT_ALGO,
) -> str:
    """Compute a keyed HMAC hexadecimal digest.

    Parameters
    ----------
    key : bytes | bytearray | memoryview | str
        Secret key for HMAC generation.
    data : bytes | bytearray | memoryview | str
        Payload to authenticate.
    algo : str, optional
        Digest algorithm from SUPPORTED_ALGOS. Default is 'sha256'.

    Returns
    -------
    str
        Lowercase hexadecimal HMAC digest.
    """
    if algo not in SUPPORTED_ALGOS:
        raise ValueError(
            f"unsupported algo {algo!r}; expected one of {sorted(SUPPORTED_ALGOS)}"
        )
    if isinstance(key, str):
        key_bytes = key.encode("utf-8")
    elif isinstance(key, (bytes, bytearray, memoryview)):
        key_bytes = bytes(memoryview(key).cast("B"))
    else:
        raise TypeError(f"key must be bytes-like or str, got {type(key).__name__}")

    if isinstance(data, str):
        data_bytes = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray, memoryview)):
        data_bytes = bytes(memoryview(data).cast("B"))
    else:
        raise TypeError(f"data must be bytes-like or str, got {type(data).__name__}")

    return hmac.new(key_bytes, data_bytes, digestmod=algo).hexdigest()


def verify_hmac(
    key: bytes | bytearray | memoryview | str,
    data: bytes | bytearray | memoryview | str,
    expected_digest: str,
    *,
    algo: str = DEFAULT_ALGO,
) -> bool:
    """Verify an HMAC digest in constant time.

    Parameters
    ----------
    key : bytes | bytearray | memoryview | str
        Secret key.
    data : bytes | bytearray | memoryview | str
        Payload.
    expected_digest : str
        Hexadecimal HMAC digest to compare against.
    algo : str, optional
        Digest algorithm. Default is 'sha256'.

    Returns
    -------
    bool
        True if the digest matches; False otherwise.
    """
    if not isinstance(expected_digest, str):
        raise TypeError("expected_digest must be a string")
    try:
        actual = hmac_digest(key, data, algo=algo)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual.casefold(), expected_digest.strip().casefold())


def _normalize_structured(
    obj: Any,
) -> Any:
    if isinstance(obj, (bytes, bytearray, memoryview)):
        return {"__bytes__": bytes(memoryview(obj).cast("B")).hex()}
    if isinstance(obj, dict):
        return {k: _normalize_structured(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_structured(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_normalize_structured(v) for v in obj)
    if isinstance(obj, (set, frozenset)):
        return set(_normalize_structured(v) for v in obj)
    return obj


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
    return content_hash(
        canonical_json(_normalize_structured(value)),
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
    OSError
        If a directory cannot be enumerated or a file cannot be read.
    ValueError
        If a directory changes identity during traversal.
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

    #? pathlib.rglob suppresses enumeration errors, which can turn an unreadable
    #? subtree into a seemingly complete empty manifest. Explicit scans propagate
    #? errors and never classify entries by following symbolic links.
    pending = [(base, base.stat())]
    files: list[pathlib.Path] = []
    while pending:
        directory, expected = pending.pop()
        current = directory.lstat()
        if not stat.S_ISDIR(current.st_mode) or not os.path.samestat(current, expected):
            raise ValueError("directory changed during manifest traversal")
        with os.scandir(directory) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                path = directory / entry.name
                if stat.S_ISDIR(info.st_mode):
                    pending.append((path, info))
                elif stat.S_ISREG(info.st_mode):
                    files.append(path)
        if not os.path.samestat(directory.lstat(), expected):
            raise ValueError("directory changed during manifest traversal")
    files.sort(key=lambda path: path.relative_to(base).as_posix())

    manifest: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(base).as_posix()
        #? Do not silently produce a partial integrity manifest when a file
        #? changes or secure opening rejects a previously enumerated path.
        #? Symlinks are already excluded during enumeration.
        with security.open_path_under_base(
            str(base),
            relative,
            mode="rb",
        ) as handle:
            manifest[relative] = _hash_binary_handle(
                cast(BinaryIO, handle),
                algo=algo,
                chunk_size=chunk_size,
            )
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


def murmurhash3_32(
    data: bytes | str,
    seed: int = 0,
) -> int:
    """Compute 32-bit MurmurHash3 digest."""
    if isinstance(data, str):
        buf = data.encode("utf-8")
    elif isinstance(data, (bytes, bytearray, memoryview)):
        buf = bytes(data)
    else:
        raise TypeError(f"data must be bytes or str, got {type(data).__name__}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")

    length = len(buf)
    nblocks = length // 4
    h1 = seed & 0xFFFFFFFF
    c1 = 0xCC9E2D51
    c2 = 0x1B873593

    for i in range(nblocks):
        idx = i * 4
        k1 = buf[idx] | (buf[idx + 1] << 8) | (buf[idx + 2]
                         << 16) | (buf[idx + 3] << 24)
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF

        h1 ^= k1
        h1 = ((h1 << 13) | (h1 >> 19)) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0xE6546B64) & 0xFFFFFFFF

    tail_idx = nblocks * 4
    rem = length & 3
    k1 = 0
    if rem == 3:
        k1 ^= buf[tail_idx + 2] << 16
    if rem >= 2:
        k1 ^= buf[tail_idx + 1] << 8
    if rem >= 1:
        k1 ^= buf[tail_idx]
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = ((k1 << 15) | (k1 >> 17)) & 0xFFFFFFFF
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    h1 ^= length
    h1 ^= (h1 >> 16)
    h1 = (h1 * 0x85EBCA6B) & 0xFFFFFFFF
    h1 ^= (h1 >> 13)
    h1 = (h1 * 0xC2B2AE35) & 0xFFFFFFFF
    h1 ^= (h1 >> 16)
    return h1


def fnv1a_32(
    data: bytes | str,
) -> int:
    """Compute 32-bit Fowler-Noll-Vo FNV-1a hash."""
    buf = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    h = 0x811C9DC5
    for b in buf:
        h = (h ^ b) & 0xFFFFFFFF
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def fnv1a_64(
    data: bytes | str,
) -> int:
    """Compute 64-bit Fowler-Noll-Vo FNV-1a hash."""
    buf = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    h = 0xCBF29CE484222325
    for b in buf:
        h = (h ^ b) & 0xFFFFFFFFFFFFFFFF
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def rabin_karp_hash(
    data: bytes | str,
    *,
    base: int = 256,
    prime: int = 1_000_000_007,
) -> int:
    """Calculate polynomial hash of a sequence for Rabin-Karp matching."""
    buf = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    h = 0
    for b in buf:
        h = (h * base + b) % prime
    return h


class RollingHash:
    """Rabin-Karp sliding window polynomial rolling hash."""

    def __init__(self,
        window_size: int,
        *,
        base: int = 256,
        prime: int = 1_000_000_007,
    ) -> None:
        if isinstance(
    window_size,
    bool) or not isinstance(
        window_size,
         int) or window_size < 1:
            raise ValueError("window_size must be a positive integer")
        self.window_size = window_size
        self.base = base
        self.prime = prime
        self.high_multiplier = pow(base, window_size - 1, prime)
        self.hash_value = 0

    def feed(self,
        data: bytes | str,
    ) -> int:
        """Seed the rolling hash with an initial window sequence."""
        buf = data.encode("utf-8") if isinstance(data, str) else bytes(data)
        h = 0
        for b in buf:
            h = (h * self.base + b) % self.prime
        self.hash_value = h
        return h

    def slide(self,
        out_byte: int,
        in_byte: int,
    ) -> int:
        """Slide window forward by removing out_byte and adding in_byte."""
        h = (self.hash_value - out_byte * self.high_multiplier) % self.prime
        h = (h * self.base + in_byte) % self.prime
        self.hash_value = h
        return h

    @property
    def digest(self) -> int:
        """Return the current rolling hash integer."""
        return self.hash_value


def sha256_digest(
    data: bytes | str,
    *,
    as_hex: bool = True,
) -> str | bytes:
    """Calculate SHA-256 digest directly from string or bytes."""
    buf = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    d = hashlib.sha256(buf)
    return d.hexdigest() if as_hex else d.digest()


def hmac_sha256(
    key: bytes | str,
    data: bytes | str,
    *,
    as_hex: bool = True,
) -> str | bytes:
    """Calculate HMAC-SHA256 digest from key and payload."""
    k = key.encode("utf-8") if isinstance(key, str) else bytes(key)
    buf = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    mac = hmac.new(k, buf, hashlib.sha256)
    return mac.hexdigest() if as_hex else mac.digest()


def compute_file_checksum(
    path: str | pathlib.Path,
    *,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute hex digest for a file path using a streaming buffer."""
    return file_hash(path, algo=algorithm, chunk_size=chunk_size)


def verify_file_checksum(
    path: str | pathlib.Path,
    expected_digest: str,
    *,
    algorithm: str = "sha256",
) -> bool:
    """Verify that file digest matches expected digest in constant time."""
    actual = compute_file_checksum(path, algorithm=algorithm)
    return hmac.compare_digest(actual.lower(), expected_digest.strip().lower())


class MerkleTree:
    """Binary Merkle tree implementation with root hash and audit proof generation."""

    def __init__(self,
        leaves: Iterable[bytes | str],
        *,
        hash_algo: str = "sha256",
    ) -> None:
        if hash_algo not in SUPPORTED_ALGOS:
            raise ValueError(f"unsupported hash algorithm {hash_algo!r}")
        self.hash_algo = hash_algo
        leaf_list: list[str] = []
        for leaf in leaves:
            buf = leaf.encode("utf-8") if isinstance(leaf, str) else bytes(leaf)
            leaf_list.append(hashlib.new(hash_algo, buf).hexdigest())
        if not leaf_list:
            raise ValueError("MerkleTree requires at least one leaf")
        self.leaves = leaf_list
        self.levels: list[list[str]] = [self.leaves]
        self._build_tree()

    def _hash_pair(self,
        left: str,
        right: str,
    ) -> str:
        combined = (left + right).encode("ascii")
        return hashlib.new(self.hash_algo, combined).hexdigest()

    def _build_tree(self) -> None:
        current = self.leaves
        while len(current) > 1:
            next_level: list[str] = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else left
                next_level.append(self._hash_pair(left, right))
            self.levels.append(next_level)
            current = next_level

    @property
    def root(self) -> str:
        """Return the Merkle root hex digest."""
        return self.levels[-1][0]

    def get_proof(self,
        leaf_index: int,
    ) -> list[tuple[str, str]]:
        """Return audit proof: list of ('left'|'right', sibling_hash)."""
        if (
            isinstance(leaf_index, bool)
            or not isinstance(leaf_index, int)
            or not (0 <= leaf_index < len(self.leaves))
        ):
            raise IndexError("leaf_index out of bounds")
        proof: list[tuple[str, str]] = []
        idx = leaf_index
        for level in self.levels[:-1]:
            is_right_sibling = (idx % 2 == 0)
            if is_right_sibling:
                sibling_idx = idx + 1 if idx + 1 < len(level) else idx
                direction = "right"
            else:
                sibling_idx = idx - 1
                direction = "left"
            proof.append((direction, level[sibling_idx]))
            idx //= 2
        return proof

    @classmethod
    def verify_proof(cls,
        leaf: bytes | str,
        proof: list[tuple[str, str]],
        root: str,
        *,
        hash_algo: str = "sha256",
    ) -> bool:
        """Verify an audit proof against a known Merkle root."""
        buf = leaf.encode("utf-8") if isinstance(leaf, str) else bytes(leaf)
        curr = hashlib.new(hash_algo, buf).hexdigest()
        for direction, sibling in proof:
            combined = (sibling + curr) if direction == "left" else (curr + sibling)
            curr = hashlib.new(hash_algo, combined.encode("ascii")).hexdigest()
        return hmac.compare_digest(curr, root)

