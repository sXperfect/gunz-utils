"""Dependency-free content-addressed local file storage."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import errno
import hashlib
import io
import os
import secrets
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .hashing import DEFAULT_ALGO, SUPPORTED_ALGOS
from .streaming import copy_and_hash

_ANCHORED_IO = (
    os.name == "posix"
    and hasattr(os, "O_NOFOLLOW")
    and all(
        function in os.supports_dir_fd
        for function in (os.open, os.mkdir, os.stat, os.link, os.unlink, os.rename)
    )
)

_CONTENT_ID_ALGOS = frozenset({"sha256", "sha512", "sha3_256", "blake2b", "blake2s"})


@contextmanager
def _publication_lock(
    path: Path,
) -> Iterator[None]:
    """Serialize cooperating publishers through a symlink-safe file lock.

    Parameters
    ----------
    path : Path
        path parameter.

    Returns
    -------
    Iterator[None]
        The result of the operation.
    """
    if path.is_symlink():
        raise ValueError("content-addressed publication lock must not be a symlink")
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        descriptor_info = os.fstat(descriptor)
        path_info = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(descriptor_info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or not os.path.samestat(descriptor_info, path_info)
        ):
            raise ValueError(
                "content-addressed publication lock must be a regular file"
            )

        if os.name == "nt":
            import msvcrt

            windows_runtime = cast(Any, msvcrt)
            if descriptor_info.st_size == 0:
                os.write(descriptor, b"\0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            windows_runtime.locking(descriptor, windows_runtime.LK_LOCK, 1)
            try:
                yield
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                windows_runtime.locking(descriptor, windows_runtime.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


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

    POSIX systems with descriptor-relative operations anchor fanout traversal and
    publication. The configured root and destination ancestors must be trusted; callers
    must prevent concurrent mutation of stored file contents. Other platforms
    require trusted store and destination directory trees. Returned paths are
    snapshots and cannot guarantee identity after a subsequent filesystem change.

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
        """Return hexadecimal digest length for the configured algorithm.

        Returns
        -------
        int
            The result of the operation.
        """
        return hashlib.new(self.algo).digest_size * 2

    def _validate_digest(self,
        digest: str,
    ) -> str:
        """Validate and normalize a hexadecimal digest.

        Parameters
        ----------
        digest : str
            digest parameter.

        Returns
        -------
        str
            The result of the operation.
        """
        if not isinstance(digest, str):
            raise TypeError("digest must be a string")
        normalized = digest.casefold()
        if len(normalized) != self.digest_chars:
            raise ValueError(
                f"digest must contain {self.digest_chars} hexadecimal characters"
            )
        if any(character not in "0123456789abcdef" for character in normalized):
            raise ValueError("digest must be hexadecimal")
        return normalized

    def path_for(self,
        digest: str,
    ) -> Path:
        """Return the canonical store path for a validated digest.

        Parameters
        ----------
        digest : str
            digest parameter.

        Returns
        -------
        Path
            The result of the operation.
        """
        normalized = self._validate_digest(digest)
        target = self.root
        for level in range(self.fanout_levels):
            start = level * self.fanout_chars
            stop = start + self.fanout_chars
            target = target / normalized[start:stop]
        return target / normalized

    @contextmanager
    def _parent_handle(self,
        target: Path,
        *,
        create: bool,
    ) -> Iterator[int | None]:
        """Anchor fanout traversal; root ancestors must be trusted.

        Parameters
        ----------
        target : Path
            target parameter.
        create : bool
            create parameter.

        Returns
        -------
        Iterator[int | None]
            The result of the operation.
        """
        if not _ANCHORED_IO:
            self._check_prefix_path(target, create=create)
            yield None
            return
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for component in target.parent.relative_to(self.root).parts:
                if create:
                    try:
                        os.mkdir(component, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                try:
                    child = os.open(
                        component,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=descriptor,
                    )
                except OSError as exc:
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                        raise ValueError(
                            "content-addressed prefix directory must not be "
                            "a symlink or non-directory"
                        ) from exc
                    raise
                os.close(descriptor)
                descriptor = child
            yield descriptor
        finally:
            os.close(descriptor)

    @staticmethod
    def _check_directory_identity(
        path: Path,
        descriptor: int | None,
    ) -> None:
        """_check_directory_identity() function.

        Parameters
        ----------
        path : Path
            path parameter.
        descriptor : int | None
            descriptor parameter.
        """
        if descriptor is not None:
            info = os.stat(path, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode) or not os.path.samestat(
                info, os.fstat(descriptor)
            ):
                raise ValueError("publication directory changed during operation")

    @staticmethod
    def _check_file_identity(
        path: Path,
        descriptor: int,
        parent_fd: int | None,
    ) -> None:
        """_check_file_identity() function.

        Parameters
        ----------
        path : Path
            path parameter.
        descriptor : int
            descriptor parameter.
        parent_fd : int | None
            parent_fd parameter.
        """
        info = os.stat(
            path.name if parent_fd is not None else path,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISREG(info.st_mode) or not os.path.samestat(
            info, os.fstat(descriptor)
        ):
            raise ValueError("artifact changed during operation")

    @staticmethod
    def _temporary_file(
        parent: Path,
        parent_fd: int | None,
        prefix: str,
    ) -> tuple[int, Path]:
        """_temporary_file() function.

        Parameters
        ----------
        parent : Path
            parent parameter.
        parent_fd : int | None
            parent_fd parameter.
        prefix : str
            prefix parameter.

        Returns
        -------
        tuple[int, Path]
            The result of the operation.
        """
        if parent_fd is None:
            descriptor, name = tempfile.mkstemp(
                dir=parent, prefix=prefix, suffix=".tmp"
            )
            return descriptor, Path(name)
        while True:
            name = prefix + secrets.token_hex(16) + ".tmp"
            try:
                descriptor = os.open(
                    name,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent_fd,
                )
            except FileExistsError:
                continue
            return descriptor, parent / name

    @staticmethod
    def _unlink(
        path: Path,
        parent_fd: int | None,
    ) -> None:
        """_unlink() function.

        Parameters
        ----------
        path : Path
            path parameter.
        parent_fd : int | None
            parent_fd parameter.
        """
        try:
            os.unlink(path.name if parent_fd is not None else path, dir_fd=parent_fd)
        except FileNotFoundError:
            pass

    @staticmethod
    @contextmanager
    def _duplicate_handle(
        descriptor: int,
        mode: str,
    ) -> Iterator[BinaryIO]:
        """_duplicate_handle() function.

        Parameters
        ----------
        descriptor : int
            descriptor parameter.
        mode : str
            mode parameter.

        Returns
        -------
        Iterator[BinaryIO]
            The result of the operation.
        """
        duplicate = os.dup(descriptor)
        try:
            handle = os.fdopen(duplicate, mode)
        except BaseException:
            os.close(duplicate)
            raise
        with handle:
            yield cast(BinaryIO, handle)

    def _verify_handle(self,
        descriptor: int,
        digest: str,
        size_bytes: int | None = None,
    ) -> None:
        """_verify_handle() function.

        Parameters
        ----------
        descriptor : int
            descriptor parameter.
        digest : str
            digest parameter.
        size_bytes : int | None
            size_bytes parameter.
        """
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("content-addressed target is not a regular file")
        if size_bytes is not None and info.st_size != size_bytes:
            raise ValueError(f"content-addressed artifact is corrupted: {digest}")
        hasher = hashlib.new(self.algo)
        os.lseek(descriptor, 0, os.SEEK_SET)
        while block := os.read(descriptor, self.chunk_size):
            hasher.update(block)
        os.lseek(descriptor, 0, os.SEEK_SET)
        if hasher.hexdigest() != digest:
            raise ValueError(f"content-addressed artifact is corrupted: {digest}")

    @contextmanager
    def _artifact_handle(self,
        target: Path,
        parent_fd: int | None,
    ) -> Iterator[int]:
        """_artifact_handle() function.

        Parameters
        ----------
        target : Path
            target parameter.
        parent_fd : int | None
            parent_fd parameter.

        Returns
        -------
        Iterator[int]
            The result of the operation.
        """
        if parent_fd is None and target.is_symlink():
            raise ValueError("content-addressed artifact path is a symlink")
        flags = (
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
        try:
            descriptor = os.open(
                target.name if parent_fd is not None else target,
                flags,
                dir_fd=parent_fd,
            )
        except OSError as exc:
            if exc.errno == errno.ELOOP:
                raise ValueError(
                    "content-addressed artifact path is a symlink"
                ) from exc
            raise
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("content-addressed target is not a regular file")
            yield descriptor
        finally:
            os.close(descriptor)

    def _check_prefix_path(self,
        target: Path,
        *,
        create: bool,
    ) -> None:
        """Reject symlinked/non-directory fanout components below the root.

        Parameters
        ----------
        target : Path
            target parameter.
        create : bool
            create parameter.
        """
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
                raise ValueError("content-addressed prefix path must be a directory")

    def _publish_temporary(self,
        temporary: Path,
        digest: str,
        size_bytes: int,
        *,
        temporary_fd: int | None = None,
        root_fd: int | None = None,
    ) -> StoredArtifact:
        """Publish into an anchored fanout, retaining the verified staging inode.

        Parameters
        ----------
        temporary : Path
            temporary parameter.
        digest : str
            digest parameter.
        size_bytes : int
            size_bytes parameter.
        temporary_fd : int | None
            temporary_fd parameter.
        root_fd : int | None
            root_fd parameter.

        Returns
        -------
        StoredArtifact
            The result of the operation.
        """
        target = self.path_for(digest)
        with self._parent_handle(target, create=True) as parent_fd:
            lock_path = target.parent / ".publish.lock"
            with _publication_lock(lock_path):
                if temporary_fd is not None:
                    self._check_file_identity(temporary, temporary_fd, root_fd)
                try:
                    os.link(
                        temporary.name if root_fd is not None else temporary,
                        target.name if parent_fd is not None else target,
                        src_dir_fd=root_fd,
                        dst_dir_fd=parent_fd,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    with self._artifact_handle(target, parent_fd) as descriptor:
                        self._verify_handle(descriptor, digest, size_bytes)
                except OSError:
                    try:
                        with self._artifact_handle(target, parent_fd) as descriptor:
                            self._verify_handle(descriptor, digest, size_bytes)
                    except FileNotFoundError:
                        #? Same-digest cooperating writers may replace the winner inode;
                        #? fallback promises correct content, not inode preservation.
                        os.replace(
                            temporary.name if root_fd is not None else temporary,
                            target.name if parent_fd is not None else target,
                            src_dir_fd=root_fd,
                            dst_dir_fd=parent_fd,
                        )
                self._check_prefix_path(target, create=False)
                self._check_directory_identity(target.parent, parent_fd)
                with self._artifact_handle(target, parent_fd) as descriptor:
                    self._verify_handle(descriptor, digest, size_bytes)
        return StoredArtifact(digest=digest, path=target, size_bytes=size_bytes)

    def put_stream(self,
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

        root_fd = None
        if _ANCHORED_IO:
            root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            descriptor, temporary = self._temporary_file(
                self.root, root_fd, ".incoming."
            )
            try:
                with self._duplicate_handle(descriptor, "wb") as target_handle:
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
                    temporary_fd=descriptor,
                    root_fd=root_fd,
                )
            finally:
                os.close(descriptor)
                self._unlink(temporary, root_fd)
        finally:
            if root_fd is not None:
                os.close(root_fd)

    def put_bytes(self,
        data: bytes | bytearray | memoryview,
    ) -> StoredArtifact:
        """Store an in-memory byte buffer without an intermediate source file.

        Parameters
        ----------
        data : bytes | bytearray | memoryview
            data parameter.

        Returns
        -------
        StoredArtifact
            The result of the operation.
        """
        if not isinstance(data, bytes | bytearray | memoryview):
            raise TypeError("data must be bytes-like")
        with io.BytesIO(bytes(data)) as source:
            return self.put_stream(source)

    def put(self,
        source: str | Path,
    ) -> StoredArtifact:
        """Store one regular file without following a final-component symlink.

        Parameters
        ----------
        source : str | Path
            source parameter.

        Returns
        -------
        StoredArtifact
            The result of the operation.
        """
        item = Path(source)
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
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

    def materialize(self,
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
        A concurrent staging-name substitution is detected, but detection after
        publication may leave the substituted destination entry. Callers requiring
        destination identity on failure must use a trusted destination parent;
        arbitrary directory writers can also mutate returned paths after success.
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

        normalized = self._validate_digest(digest)
        source = self.path_for(normalized)
        target = Path(destination)
        destination_fd = None
        try:
            with self._parent_handle(source, create=False) as source_parent_fd:
                with self._artifact_handle(source, source_parent_fd) as source_fd:
                    if verify:
                        self._verify_handle(source_fd, normalized)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if _ANCHORED_IO:
                        destination_fd = os.open(
                            target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                        )
                    if not replace:
                        try:
                            os.stat(
                                target.name if destination_fd is not None else target,
                                dir_fd=destination_fd,
                                follow_symlinks=False,
                            )
                        except FileNotFoundError:
                            pass
                        else:
                            raise FileExistsError(target)
                    descriptor, temporary = self._temporary_file(
                        target.parent, destination_fd, f".{target.name}."
                    )
                    try:
                        linked = False
                        if strategy == "hardlink":
                            #? Link to a fresh exclusive name; never reopen a removed
                            #? reservation for copying. Keep source descriptor pinned.
                            link_path = target.parent / (
                                f".{target.name}." + secrets.token_hex(16) + ".link"
                            )
                            link_created = False
                            try:
                                os.link(
                                    source.name
                                    if source_parent_fd is not None
                                    else source,
                                    link_path.name
                                    if destination_fd is not None
                                    else link_path,
                                    src_dir_fd=source_parent_fd,
                                    dst_dir_fd=destination_fd,
                                    follow_symlinks=False,
                                )
                                link_created = True
                                self._check_file_identity(
                                    link_path, source_fd, destination_fd
                                )
                            except OSError:
                                if not fallback_copy:
                                    raise
                            else:
                                self._unlink(temporary, destination_fd)
                                temporary = link_path
                                linked = True
                            finally:
                                if link_created and not linked:
                                    self._unlink(link_path, destination_fd)
                        if not linked:
                            with self._duplicate_handle(
                                source_fd, "rb"
                            ) as source_handle:
                                with self._duplicate_handle(
                                    descriptor, "wb"
                                ) as target_handle:
                                    shutil.copyfileobj(
                                        source_handle, target_handle, self.chunk_size
                                    )
                                    target_handle.flush()
                            source_info = os.fstat(source_fd)
                            if hasattr(os, "fchmod"):
                                os.fchmod(descriptor, stat.S_IMODE(source_info.st_mode))
                            else:
                                #? Platforms without descriptor permissions require
                                #? the documented trusted destination tree.
                                os.chmod(temporary, stat.S_IMODE(source_info.st_mode))
                            if os.utime in os.supports_fd:
                                os.utime(
                                    descriptor,
                                    ns=(
                                        source_info.st_atime_ns,
                                        source_info.st_mtime_ns,
                                    ),
                                )
                        self._check_file_identity(
                            temporary,
                            source_fd if linked else descriptor,
                            destination_fd,
                        )
                        self._check_directory_identity(target.parent, destination_fd)
                        if replace:
                            os.replace(
                                temporary.name
                                if destination_fd is not None
                                else temporary,
                                target.name if destination_fd is not None else target,
                                src_dir_fd=destination_fd,
                                dst_dir_fd=destination_fd,
                            )
                        else:
                            os.link(
                                temporary.name
                                if destination_fd is not None
                                else temporary,
                                target.name if destination_fd is not None else target,
                                src_dir_fd=destination_fd,
                                dst_dir_fd=destination_fd,
                                follow_symlinks=False,
                            )
                        self._check_file_identity(
                            target, source_fd if linked else descriptor, destination_fd
                        )
                        self._check_directory_identity(target.parent, destination_fd)
                    finally:
                        os.close(descriptor)
                        self._unlink(temporary, destination_fd)
        except FileNotFoundError as exc:
            if not source.exists():
                raise KeyError(normalized) from exc
            raise
        finally:
            if destination_fd is not None:
                os.close(destination_fd)
        return target

    def get(self,
        digest: str,
        *,
        verify: bool = True,
    ) -> Path:
        """Return a stored artifact path, optionally verifying its digest.

        A concurrent pathname replacement can raise ValueError even when the
        replacement has the same content digest. Callers may retry after
        cooperating publication settles. Returned paths remain snapshots.

        Parameters
        ----------
        digest : str
            digest parameter.
        verify : bool
            verify parameter.

        Returns
        -------
        Path
            The result of the operation.
        """
        if not isinstance(verify, bool):
            raise ValueError("verify must be bool")
        normalized = self._validate_digest(digest)
        target = self.path_for(normalized)
        try:
            with self._parent_handle(target, create=False) as parent_fd:
                with self._artifact_handle(target, parent_fd) as descriptor:
                    if verify:
                        self._verify_handle(descriptor, normalized)
                    self._check_file_identity(target, descriptor, parent_fd)
                self._check_prefix_path(target, create=False)
                self._check_directory_identity(target.parent, parent_fd)
        except FileNotFoundError:
            raise KeyError(normalized) from None
        return target

    def verify(self,
        digest: str,
    ) -> bool:
        """Return whether an artifact exists and matches its content digest.

        Parameters
        ----------
        digest : str
            digest parameter.

        Returns
        -------
        bool
            The result of the operation.
        """
        try:
            self.get(
                digest,
                verify=True,
            )
        except (KeyError, ValueError, OSError):
            return False
        return True


__all__ = ["ContentAddressedStore", "StoredArtifact"]
