"""Crash-safe file writing utilities for the Gunz ecosystem."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import contextlib
import importlib
import os
import pathlib
import re
import stat
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from ._version import __version__ as __version__
from .serialization import decode_json_object, json_dumps

try:
    _accel = importlib.import_module("._accel", package=__package__)
    _accel_physical_lines: Callable[[str, bool], list[str]] | None = getattr(
        _accel, "fast_physical_lines", None
    )
except (ImportError, AttributeError):  # pragma: no cover
    _accel_physical_lines = None

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"
__all__ = [
    "FileSnapshot",
    "atomic_json_read",
    "atomic_json_write",
    "atomic_write",
    "physical_lines",
    "read_file_snapshot",
    "read_regular_bytes",
    "read_source_file",
    "safe_read_bytes",
    "safe_read_text",
]


def atomic_write(
    path: str | pathlib.Path,
    content: str | bytes | bytearray | memoryview,
    *,
    mode: str = "w",
    encoding: str | None = None,
    mkdir: bool = False,
    durable: bool = False,
    permissions: int | None = None,
) -> None:
    """Atomically write text or bytes through a same-directory temporary file.

    When permissions is provided, the temporary file receives that mode before
    any content is written, and the mode is preserved by atomic replacement.

    With ``durable=True`` the file is fsynced before replacement and the parent
    directory is fsynced afterwards. If that final directory fsync fails, the
    replacement may already be visible even though durability was not confirmed
    and this function raises.
    """
    if not isinstance(path, str | pathlib.Path):
        raise TypeError("path must be str or pathlib.Path")
    if not isinstance(mkdir, bool):
        raise TypeError("mkdir must be bool")
    if not isinstance(durable, bool):
        raise TypeError("durable must be bool")
    if not isinstance(content, (str, bytes, bytearray, memoryview)):
        raise TypeError(
            f"content must be str or bytes-like, got {type(content).__name__}"
        )

    if mode not in ("w", "wb"):
        raise ValueError("mode must be 'w' or 'wb'")
    is_binary = mode == "wb"
    if is_binary and isinstance(content, str):
        raise ValueError("Binary mode requires bytes content")
    if not is_binary and isinstance(content, (bytes, bytearray, memoryview)):
        raise ValueError("Text mode requires str content")
    if not is_binary and encoding is not None and not isinstance(encoding, str):
        raise TypeError("encoding must be str or None")

    if permissions is not None:
        if (
            isinstance(permissions, bool)
            or not isinstance(permissions, int)
            or not 0 <= permissions <= 0o7777
        ):
            raise ValueError(
                "permissions must be an integer mode in the range 0..0o7777"
            )
        if not hasattr(os, "fchmod"):
            raise NotImplementedError(
                "explicit permissions require os.fchmod support"
            )

    target = pathlib.Path(path)
    if target.is_dir():
        raise IsADirectoryError(f"target path is an existing directory: {target}")

    if mkdir:
        #? Security (VULN-2026-002): when the target is owner-private,
        #? create missing parent directories with owner-private permissions too.
        private_target = (
            permissions is not None
            and (permissions & 0o077) == 0
        )
        dir_mode = 0o700 if private_target else 0o755
        target.parent.mkdir(parents=True, exist_ok=True, mode=dir_mode)
    elif not target.parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {target.parent}")

    write_payload: bytes | str
    if is_binary and isinstance(content, (bytearray, memoryview)):
        write_payload = bytes(memoryview(content).cast("B"))
    else:
        write_payload = content

    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        if permissions is not None:
            os.fchmod(
                fd,
                permissions,
            )
        file_handle = os.fdopen(
            fd, mode, encoding=None if is_binary else encoding or "utf-8",
            closefd=False,
        )
        #? Keep raw ownership even if wrapper construction closes an incomplete
        #? wrapper before raising (for example for an unknown text encoding).
        with file_handle as file:
            file.write(write_payload)
            if durable:
                file.flush()
                os.fsync(file.fileno())
        os.replace(tmp_path, target)
        if durable and hasattr(os, "O_DIRECTORY"):
            dir_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
    finally:
        os.close(fd)


def atomic_json_write(
    path: str | pathlib.Path,
    value: Any,
    *,
    pretty: bool = True,
    mkdir: bool = False,
    durable: bool = False,
    permissions: int | None = None,
) -> None:
    """Serialize deterministic JSON and publish it atomically.

    Parameters
    ----------
    path : str | pathlib.Path
        Destination JSON path.
    value : Any
        Value accepted by gunz_utils.serialization.to_jsonable.
    pretty : bool, default=True
        Use indented JSON when true.
    mkdir : bool, default=False
        Create missing parent directories.
    durable : bool, default=False
        Flush file and parent-directory metadata before returning.
    permissions : int | None, default=None
        Explicit file mode applied before content is written.
    """
    atomic_write(
        path,
        json_dumps(value, pretty=pretty),
        mode="w",
        encoding="utf-8",
        mkdir=mkdir,
        durable=durable,
        permissions=permissions,
    )


def atomic_json_read(
    path: str | pathlib.Path,
    *,
    max_bytes: int = 64 * 1024 * 1024,
    max_depth: int = 64,
) -> Any:
    """Read and parse a JSON file safely.

    Verifies regular file status, bounds file size, enforces UTF-8 decoding,
    and forbids duplicate keys and non-finite numbers (NaN/Infinity).

    Parameters
    ----------
    path : str | pathlib.Path
        JSON file to read.
    max_bytes : int, default=64 MiB
        Maximum file size in bytes to prevent memory exhaustion.
    max_depth : int, default=64
        Maximum allowed JSON nesting depth.

    Returns
    -------
    Any
        Parsed JSON object.
    """
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth <= 0:
        raise ValueError("max_depth must be a positive integer")

    target = pathlib.Path(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    fd = os.open(target, flags)
    try:
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode):
            raise IsADirectoryError(f"path {target} is a directory")
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"path {target} must be a regular file")
        if st.st_size > max_bytes:
            raise ValueError(f"file size {st.st_size} exceeds max_bytes {max_bytes}")
        with os.fdopen(fd, "rb") as f:
            fd = -1
            raw = f.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise ValueError(f"file size exceeds max_bytes {max_bytes}")
    finally:
        if fd >= 0:
            os.close(fd)

    return decode_json_object(raw, max_depth=max_depth)


def safe_read_bytes(
    path: str | pathlib.Path,
    *,
    allow_symlink: bool = True,
    max_bytes: int | None = None,
) -> bytes:
    """Read a regular file into bytes with size bounds and symlink policy.

    Parameters
    ----------
    path : str | pathlib.Path
        Path of the file to read.
    allow_symlink : bool, default=True
        Whether to allow reading through symlinks. When False, symlinks are rejected.
    max_bytes : int | None, default=None
        Maximum bytes to read before raising ValueError.

    Returns
    -------
    bytes
        File contents.
    """
    if not isinstance(allow_symlink, bool):
        raise TypeError("allow_symlink must be bool")
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError("max_bytes must be a positive integer or None")

    target = pathlib.Path(path)
    if not allow_symlink and target.is_symlink():
        raise ValueError(f"path {target} is a symlink")

    flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if not allow_symlink and hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        fd = os.open(target, flags)
    except OSError as exc:
        if not allow_symlink and target.is_symlink():
            raise ValueError(f"path {target} is a symlink") from exc
        raise

    try:
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode):
            raise IsADirectoryError(f"path {target} is a directory")
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(f"path {target} must be a regular file")
        if max_bytes is not None and st.st_size > max_bytes:
            raise ValueError(f"file size {st.st_size} exceeds max_bytes {max_bytes}")
        chunks: list[bytes] = []
        remaining = max_bytes
        while True:
            read_size = min(remaining, 1 << 20) if remaining is not None else (1 << 20)
            chunk = os.read(fd, read_size)
            if not chunk:
                break
            chunks.append(chunk)
            if remaining is not None:
                remaining -= len(chunk)
                if remaining < 0:
                    raise ValueError(f"file size exceeds max_bytes {max_bytes}")
        return b"".join(chunks)
    finally:
        os.close(fd)


def safe_read_text(
    path: str | pathlib.Path,
    *,
    encoding: str = "utf-8",
    allow_symlink: bool = True,
    max_bytes: int | None = None,
) -> str:
    """Read a regular file into decoded text with size bounds and symlink policy.

    Parameters
    ----------
    path : str | pathlib.Path
        Path of the file to read.
    encoding : str, default='utf-8'
        Text encoding.
    allow_symlink : bool, default=True
        Whether to allow reading through symlinks.
    max_bytes : int | None, default=None
        Maximum bytes to read before raising ValueError.

    Returns
    -------
    str
        Decoded file content.
    """
    raw = safe_read_bytes(path, allow_symlink=allow_symlink, max_bytes=max_bytes)
    return raw.decode(encoding)


def read_regular_bytes(
    path: str | pathlib.Path,
    *,
    max_bytes: int,
    label: str = "file",
) -> bytes:
    """Capture one bounded regular-file snapshot; never reopen it for decoding.

    The final path component must not be a symlink. Parent directories are
    trusted local paths, not a sandbox boundary. Check identity/size/timestamps
    before and after reading. A digest must be computed from these returned
    bytes, not from a separate open. This does not lock out writers or promise
    filesystem snapshots.

    Parameters
    ----------
    path : str | pathlib.Path
        Target regular file path to read.
    max_bytes : int
        Maximum permitted file size and payload bytes.
    label : str, default="file"
        Human-readable descriptor used in exception messages.

    Returns
    -------
    bytes
        Captured byte contents of the regular file.
    """
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive integer")
    target = pathlib.Path(path)
    before_path = target.lstat()
    if not stat.S_ISREG(before_path.st_mode):
        raise ValueError(f"{label} must be a non-symlink regular file")
    flags = os.O_RDONLY
    for name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK", "O_BINARY"):
        flags |= getattr(os, name, 0)
    descriptor = os.open(target, flags)
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or not os.path.samestat(before_path, before)
        ):
            raise ValueError(f"{label} path changed during open")
        if before.st_size > max_bytes:
            raise ValueError(f"{label} exceeds size limit ({max_bytes} bytes)")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1 << 20))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > max_bytes:
            raise ValueError(f"{label} exceeds size limit ({max_bytes} bytes)")
        after = os.fstat(descriptor)
        after_path = target.lstat()
        signature_before = (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        signature_after = (after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if (
            not stat.S_ISREG(after_path.st_mode)
            or not os.path.samestat(before, after_path)
            or signature_before != signature_after
            or len(payload) != after.st_size
        ):
            raise ValueError(f"{label} changed during read")
        return payload
    finally:
        os.close(descriptor)


_PHYSICAL_NEWLINE = re.compile(r"\r\n|\r|\n")
_BYTE_NEWLINE = re.compile(rb"\r\n|\r|\n")


def _stat_identity(
    metadata: os.stat_result,
) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def physical_lines(
    text: str,
    keepends: bool = False,
) -> list[str]:
    """Split text on physical newline boundaries (LF, CRLF, CR).

    Unlike str.splitlines(), this function never splits on Unicode line
    separators (such as U+2028 LINE SEPARATOR, U+2029 PARAGRAPH SEPARATOR,
    or U+0085 NEXT LINE).

    Parameters
    ----------
    text : str
        Input string to split.
    keepends : bool, default=False
        Whether to keep line terminators in returned strings.

    Returns
    -------
    list[str]
        List of split lines.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(keepends, bool):
        raise TypeError("keepends must be bool")
    if _accel_physical_lines is not None:
        return _accel_physical_lines(text, keepends)
    lines: list[str] = []
    start = 0
    for match in _PHYSICAL_NEWLINE.finditer(text):
        end = match.end() if keepends else match.start()
        lines.append(text[start:end])
        start = match.end()
    if start < len(text):
        lines.append(text[start:])
    elif not text:
        return []
    return lines


@dataclass(frozen=True, slots=True)
class FileSnapshot:
    """An immutable file snapshot capturing contents and exact stat identity."""

    path: pathlib.Path
    raw: bytes
    text: str
    encoding: str
    newline: str
    stat_identity: tuple[int, int, int, int, int, int]

    def write_if_unchanged(self,
        new_content: str | bytes,
        *,
        durable: bool = False,
    ) -> None:
        """Replace this file atomically if its on-disk identity has not changed.

        Parameters
        ----------
        new_content : str | bytes
            New content to write. If str, it will be encoded using self.encoding.
        durable : bool, default=False
            Whether to fsync the replacement file and directory.

        Raises
        ------
        OSError
            If the target changed since the snapshot, is a symlink, or write fails.
        """
        if not isinstance(durable, bool):
            raise TypeError("durable must be bool")
        if isinstance(new_content, str):
            payload = new_content.encode(self.encoding)
        elif isinstance(new_content, (bytes, bytearray)):
            payload = bytes(new_content)
        else:
            raise TypeError("new_content must be str or bytes")

        if self.path.is_symlink():
            raise OSError(f"cannot modify symbolic link: {self.path}")

        initial = self.path.lstat()
        if not stat.S_ISREG(initial.st_mode):
            raise OSError(f"target is not a regular file: {self.path}")
        if _stat_identity(initial) != self.stat_identity:
            raise OSError(f"file changed before modification: {self.path}")

        if payload == self.raw:
            return

        mode = stat.S_IMODE(initial.st_mode)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, mode)
            with os.fdopen(fd, "wb", closefd=False) as handle:
                handle.write(payload)
                if durable:
                    handle.flush()
                    os.fsync(handle.fileno())

            #? Verify target has not changed during write
            current_lstat = self.path.lstat()
            if (
                not stat.S_ISREG(current_lstat.st_mode)
                or _stat_identity(current_lstat) != self.stat_identity
            ):
                raise OSError(f"file changed during modification: {self.path}")

            os.replace(tmp_path, self.path)
            if durable and hasattr(os, "O_DIRECTORY"):
                dir_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
        finally:
            os.close(fd)


def read_file_snapshot(
    path: str | pathlib.Path,
    *,
    encoding: str | None = "utf-8",
    max_bytes: int | None = None,
) -> FileSnapshot:
    """Read a regular file once into an immutable snapshot.

    Parameters
    ----------
    path : str | pathlib.Path
        File path to read.
    encoding : str, default="utf-8"
        Text encoding to decode file contents.
    max_bytes : int | None, default=None
        Optional size bound.

    Returns
    -------
    FileSnapshot
        Immutable snapshot carrying raw bytes, decoded text, and stat signature.
    """
    target = pathlib.Path(path)
    if max_bytes is not None and (type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError("max_bytes must be a positive integer or None")

    if target.is_symlink():
        raise ValueError("path must be a non-symlink regular file")
    before_path = target.lstat()
    if not stat.S_ISREG(before_path.st_mode):
        raise ValueError("path must be a non-symlink regular file")

    flags = os.O_RDONLY
    for name in ("O_CLOEXEC", "O_NOFOLLOW", "O_NONBLOCK", "O_BINARY"):
        flags |= getattr(os, name, 0)
    fd = os.open(target, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not os.path.samestat(
            before, before_path
        ):
            raise ValueError("path must be a non-symlink regular file")
        if max_bytes is not None and before.st_size > max_bytes:
            raise ValueError(f"file exceeds size limit ({max_bytes} bytes)")

        chunks: list[bytes] = []
        remaining = (max_bytes + 1) if max_bytes is not None else None
        while remaining is None or remaining > 0:
            read_size = (
                min(remaining, 1 << 20) if remaining is not None else (1 << 20)
            )
            chunk = os.read(fd, read_size)
            if not chunk:
                break
            chunks.append(chunk)
            if remaining is not None:
                remaining -= len(chunk)
        raw = b"".join(chunks)
        if max_bytes is not None and len(raw) > max_bytes:
            raise ValueError(f"file exceeds size limit ({max_bytes} bytes)")

        after = os.fstat(fd)
        after_path = target.lstat()
        if (
            not stat.S_ISREG(after_path.st_mode)
            or _stat_identity(before) != _stat_identity(after)
            or not os.path.samestat(before, after_path)
            or len(raw) != after.st_size
        ):
            raise OSError(f"file changed while reading: {target}")
        st = after
    finally:
        os.close(fd)

    if encoding is not None:
        text = raw.decode(encoding)
        newline_match = _PHYSICAL_NEWLINE.search(text)
        newline = newline_match.group() if newline_match else "\n"
        effective_encoding = encoding
    else:
        text = ""
        newline = "\n"
        effective_encoding = "binary"
    return FileSnapshot(
        path=target,
        raw=raw,
        text=text,
        encoding=effective_encoding,
        newline=newline,
        stat_identity=_stat_identity(st),
    )


def read_source_file(
    path: str | pathlib.Path,
    *,
    max_bytes: int | None = None,
) -> FileSnapshot:
    """Read a Python source file detecting its declared encoding.

    Parameters
    ----------
    path : str | pathlib.Path
        Python source file path to read.
    max_bytes : int | None, default=None
        Optional maximum file size in bytes.

    Returns
    -------
    FileSnapshot
        Immutable snapshot with detected Python source encoding and physical newlines.
    """
    import tokenize

    target = pathlib.Path(path)
    snapshot = read_file_snapshot(
        target, encoding=None, max_bytes=max_bytes
    )
    raw = snapshot.raw
    probe = (line + b"\n" for line in _BYTE_NEWLINE.split(raw, maxsplit=2)[:2])
    detected_encoding, _ = tokenize.detect_encoding(lambda: next(probe, b""))
    text = raw.decode(detected_encoding)
    newline_match = _PHYSICAL_NEWLINE.search(text)
    newline = newline_match.group() if newline_match else "\n"
    return FileSnapshot(
        path=target,
        raw=raw,
        text=text,
        encoding=detected_encoding,
        newline=newline,
        stat_identity=snapshot.stat_identity,
    )


