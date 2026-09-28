"""Dependency-free content-addressed local file storage."""

from __future__ import annotations

import hashlib
import io
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal

from .hashing import DEFAULT_ALGO, SUPPORTED_ALGOS, file_hash
from .streaming import copy_and_hash

_CONTENT_ID_ALGOS = frozenset({"sha256", "sha512", "sha3_256", "blake2b", "blake2s"})


@dataclass(frozen=True)
class StoredArtifact:
    """One file stored under its content digest."""

    digest: str
    path: Path
    size_bytes: int


@dataclass
class ContentAddressedStore:
    """Store immutable files under content-derived paths.

    Files are placed below the store root using a digest prefix directory and
    the complete digest as the filename. Existing content is verified before
    reuse so silent corruption is distinguishable from a legitimate cache hit.

    Parameters
    ----------
    root : Path
        Store root directory.
    algo : str, optional
        Hash algorithm accepted by gunz_utils hashing/streaming helpers.
    chunk_size : int, optional
        Streaming copy and hashing block size.
    fanout_levels : int, optional
        Number of digest-prefix directory levels. Default one preserves the
        historical layout. Two levels are useful for very large stores.
    fanout_chars : int, optional
        Hex characters consumed per fanout level. Default two.
    """

    root: Path
    algo: str = DEFAULT_ALGO
    chunk_size: int = 1 << 20
    fanout_levels: int = 1
    fanout_chars: int = 2

    def __post_init__(self) -> None:
        """Normalize configuration and create the store root."""
        self.root = Path(self.root)
        if self.algo not in SUPPORTED_ALGOS:
            raise ValueError(
                f"unsupported algo {self.algo!r}; "
                f"expected one of {sorted(SUPPORTED_ALGOS)}"
            )
        if self.algo not in _CONTENT_ID_ALGOS:
            raise ValueError(
                "content-addressed storage requires a collision-resistant "
                f"algorithm; expected one of {sorted(_CONTENT_ID_ALGOS)}"
            )
        if (
            isinstance(self.chunk_size, bool)
            or not isinstance(self.chunk_size, int)
            or self.chunk_size < 1
        ):
            raise ValueError("chunk_size must be a positive integer")
        if (
            isinstance(self.fanout_levels, bool)
            or not isinstance(self.fanout_levels, int)
            or self.fanout_levels < 0
        ):
            raise ValueError("fanout_levels must be a non-negative integer")
        if (
            isinstance(self.fanout_chars, bool)
            or not isinstance(self.fanout_chars, int)
            or self.fanout_chars < 1
        ):
            raise ValueError("fanout_chars must be a positive integer")
        if self.fanout_levels * self.fanout_chars > self.digest_chars:
            raise ValueError("fanout consumes more characters than the digest")
        if self.root.is_symlink():
            raise ValueError("content-addressed store root must not be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError(
                "content-addressed store root must be a non-symlink directory"
            )

    @property
    def digest_chars(self) -> int:
        """Return hexadecimal digest length for the configured algorithm."""
        return hashlib.new(self.algo).digest_size * 2

    def _validate_digest(
        self,
        digest: str,
    ) -> str:
        """Validate and normalize a hexadecimal digest."""
        if not isinstance(digest, str):
            raise TypeError("digest must be a string")
        normalized = digest.casefold()
        if len(normalized) != self.digest_chars:
            raise ValueError(
                f"digest must contain {self.digest_chars} hexadecimal characters"
            )
        try:
            int(normalized, 16)
        except ValueError:
            raise ValueError("digest must be hexadecimal") from None
        return normalized

    def path_for(
        self,
        digest: str,
    ) -> Path:
        """Return the canonical store path for a validated digest."""
        normalized = self._validate_digest(digest)
        target = self.root
        for level in range(self.fanout_levels):
            start = level * self.fanout_chars
            stop = start + self.fanout_chars
            target = target / normalized[start:stop]
        return target / normalized

    def _verify_existing(
        self,
        target: Path,
        digest: str,
        size_bytes: int | None = None,
    ) -> None:
        """Require an existing content-addressed entry to match its identity."""
        if target.is_symlink():
            raise ValueError(
                f"content-addressed artifact path is a symlink: {digest}"
            )
        if not target.is_file():
            raise ValueError(
                "content-addressed target is not a regular file"
            )
        if size_bytes is not None and target.stat().st_size != size_bytes:
            raise ValueError(
                f"content-addressed artifact is corrupted: {digest}"
            )
        if file_hash(
            target,
            algo=self.algo,
            chunk_size=self.chunk_size,
        ) != digest:
            raise ValueError(
                f"content-addressed artifact is corrupted: {digest}"
            )

    def _check_prefix_path(
        self,
        target: Path,
        *,
        create: bool,
    ) -> None:
        """Reject symlinked/non-directory fanout components below the root."""
        if self.root.is_symlink() or not self.root.is_dir():
            raise ValueError(
                "content-addressed store root must be a non-symlink directory"
            )
        try:
            relative_parent = target.parent.relative_to(self.root)
        except ValueError:
            raise ValueError("content-addressed path escapes store root") from None

        current = self.root
        for component in relative_parent.parts:
            current = current / component
            if current.is_symlink():
                raise ValueError(
                    "content-addressed prefix directory must not be a symlink"
                )
            if create:
                current.mkdir(exist_ok=True)
            if current.exists() and not current.is_dir():
                raise ValueError(
                    "content-addressed prefix path must be a directory"
                )

    def _ensure_prefix_directory(self, target: Path) -> None:
        """Create fanout directories without accepting symlink components."""
        self._check_prefix_path(target, create=True)

    def _publish_temporary(
        self,
        temporary: Path,
        digest: str,
        size_bytes: int,
    ) -> StoredArtifact:
        """Publish one already-hashed temporary file into the store."""
        target = self.path_for(digest)

        if target.exists() or target.is_symlink():
            self._verify_existing(
                target,
                digest,
                size_bytes,
            )
            temporary.unlink(missing_ok=True)
            return StoredArtifact(
                digest=digest,
                path=target,
                size_bytes=size_bytes,
            )

        self._ensure_prefix_directory(target)

        try:
            os.link(
                temporary,
                target,
            )
        except FileExistsError:
            self._verify_existing(
                target,
                digest,
                size_bytes,
            )
        except OSError:
            # Some filesystems do not support hard-link publication. Re-check
            # for a concurrent winner before falling back to atomic replace.
            if target.exists() or target.is_symlink():
                self._verify_existing(
                    target,
                    digest,
                    size_bytes,
                )
            else:
                os.replace(
                    temporary,
                    target,
                )
                return StoredArtifact(
                    digest=digest,
                    path=target,
                    size_bytes=size_bytes,
                )
        finally:
            temporary.unlink(missing_ok=True)

        return StoredArtifact(
            digest=digest,
            path=target,
            size_bytes=size_bytes,
        )

    def put_stream(
        self,
        source: BinaryIO,
    ) -> StoredArtifact:
        """Store bytes from the current position of a readable binary stream.

        Parameters
        ----------
        source : BinaryIO
            Readable binary stream. The caller retains ownership and the stream
            is not closed by this method.

        Returns
        -------
        StoredArtifact
            Content identity and canonical object path.

        Notes
        -----
        Bytes are copied and hashed in one pass. Publication is concurrency-safe
        for cooperating writers targeting the same content digest.
        """
        if not hasattr(source, "read"):
            raise TypeError("source must provide a binary read() method")

        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.root,
            prefix=".incoming.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(
                descriptor,
                "wb",
            ) as target_handle:
                copied = copy_and_hash(
                    source,
                    target_handle,
                    algorithm=self.algo,
                    chunk_size=self.chunk_size,
                )
                target_handle.flush()
                os.fsync(target_handle.fileno())

            return self._publish_temporary(
                temporary,
                copied.hexdigest,
                copied.bytes_written,
            )
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def put_bytes(
        self,
        data: bytes | bytearray | memoryview,
    ) -> StoredArtifact:
        """Store an in-memory byte buffer without an intermediate source file."""
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        with io.BytesIO(bytes(data)) as source:
            return self.put_stream(source)

    def put(
        self,
        source: str | Path,
    ) -> StoredArtifact:
        """Store one regular file without following a final-component symlink."""
        item = Path(source)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(item, flags)
        except OSError as exc:
            if item.is_symlink():
                raise ValueError("source must be a non-symlink regular file") from exc
            raise
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("source must be a non-symlink regular file")
            with os.fdopen(descriptor, "rb") as source_handle:
                descriptor = -1
                return self.put_stream(source_handle)
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def materialize(
        self,
        digest: str,
        destination: str | Path,
        *,
        strategy: Literal["hardlink", "copy"] = "copy",
        replace: bool = False,
        verify: bool = True,
        fallback_copy: bool = True,
    ) -> Path:
        """Publish stored content at a stable compatibility path.

        Parameters
        ----------
        digest : str
            Stored content digest.
        destination : str | Path
            Compatibility/output path to create.
        strategy : {"hardlink", "copy"}, optional
            Copy by default so compatibility paths cannot mutate the immutable
            stored object. Hard links are available explicitly for consumers
            that guarantee read-only materialized paths.
        replace : bool, optional
            Atomically replace an existing destination when true. Otherwise an
            existing file/symlink raises FileExistsError.
        verify : bool, optional
            Verify the stored object digest before materialization.
        fallback_copy : bool, optional
            When hardlink creation fails (for example across filesystems), copy
            into the destination filesystem instead.

        Returns
        -------
        Path
            Materialized destination path.

        Raises
        ------
        FileExistsError
            If destination exists and replace is false.
        ValueError
            If strategy is invalid or the stored object fails validation.

        Notes
        -----
        Publication is staged in the destination directory. With replace false,
        a final hard-link publication provides atomic no-overwrite semantics.
        """
        if strategy not in {"hardlink", "copy"}:
            raise ValueError("strategy must be 'hardlink' or 'copy'")
        for name, value in (
            ("replace", replace),
            ("verify", verify),
            ("fallback_copy", fallback_copy),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be bool")

        source = self.get(
            digest,
            verify=verify,
        )
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if (target.exists() or target.is_symlink()) and not replace:
            raise FileExistsError(target)

        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.unlink(missing_ok=True)

        try:
            if strategy == "hardlink":
                try:
                    os.link(source, temporary)
                except OSError:
                    if not fallback_copy:
                        raise
                    shutil.copy2(source, temporary)
            else:
                shutil.copy2(source, temporary)

            if replace:
                os.replace(
                    temporary,
                    target,
                )
            else:
                try:
                    os.link(
                        temporary,
                        target,
                    )
                except FileExistsError:
                    raise FileExistsError(target) from None
                finally:
                    temporary.unlink(missing_ok=True)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

        return target

    def get(
        self,
        digest: str,
        *,
        verify: bool = True,
    ) -> Path:
        """Return a stored artifact path, optionally verifying its digest."""
        if not isinstance(verify, bool):
            raise ValueError("verify must be bool")
        normalized = self._validate_digest(digest)
        target = self.path_for(normalized)
        self._check_prefix_path(target, create=False)
        if not target.exists() and not target.is_symlink():
            raise KeyError(normalized)
        if verify:
            self._verify_existing(
                target,
                normalized,
            )
        elif target.is_symlink() or not target.is_file():
            raise ValueError(
                "content-addressed target is not a regular file"
            )
        return target

    def verify(
        self,
        digest: str,
    ) -> bool:
        """Return whether an artifact exists and matches its content digest."""
        try:
            self.get(
                digest,
                verify=True,
            )
        except (KeyError, ValueError, OSError):
            return False
        return True


__all__ = ["ContentAddressedStore", "StoredArtifact"]
