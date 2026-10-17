"""Production-safe filesystem helpers."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import errno
import fnmatch
import hashlib
import math
import os
import shutil
import stat
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .io import atomic_write


def contained_path(
    root: str | Path,
    path: str | Path,
) -> Path:
    """Resolve a path and require it to remain inside root.

    Parameters
    ----------
    root : str | Path
        root parameter.
    path : str | Path
        path parameter.

    Returns
    -------
    Path
        The result of the operation.
    """
    base = Path(root).resolve()
    supplied = Path(path)
    if supplied.is_absolute():
        candidate = supplied.resolve()
    else:
        candidate = (base / supplied).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise ValueError("path escapes configured root") from None
    return candidate


def lexical_contained_path(
    root: str | Path,
    path: str | Path,
) -> Path:
    """Require a relative path to remain lexically below root.

    Parameters
    ----------
    root : str | Path
        root parameter.
    path : str | Path
        path parameter.

    Returns
    -------
    Path
        The result of the operation.
    """
    supplied = Path(path)
    if supplied.is_absolute():
        raise ValueError("path must be relative")
    if any(part == ".." for part in supplied.parts):
        raise ValueError("path escapes configured root")
    return Path(root) / supplied


def atomic_write_bytes(
    path: str | Path,
    data: bytes,
) -> None:
    """Write bytes durably through the canonical atomic-write implementation.

    Parameters
    ----------
    path : str | Path
        path parameter.
    data : bytes
        data parameter.
    """
    atomic_write(
        path,
        data,
        mode="wb",
        mkdir=True,
        durable=True,
    )


def _rename_directory_noreplace(
    source: Path,
    target: Path,
) -> None:
    """Use an OS no-replace rename, failing closed when unavailable.

    Parameters
    ----------
    source : Path
        source parameter.
    target : Path
        target parameter.
    """
    if os.name == "nt":
        #? Windows rename rejects an existing destination atomically.
        os.rename(source, target)
        return

    import ctypes

    source_bytes = os.fsencode(source)
    target_bytes = os.fsencode(target)
    if b"\0" in source_bytes or b"\0" in target_bytes:
        raise ValueError("paths must not contain NUL")
    library = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux"):
        function = getattr(library, "renameat2", None)
        if function is None:
            raise NotImplementedError("atomic no-replace rename is unavailable")
        function.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint,
        ]
        function.restype = ctypes.c_int
        #? AT_FDCWD = -100; RENAME_NOREPLACE = 1.
        result = function(-100, source_bytes, -100, target_bytes, 1)
    elif sys.platform == "darwin":
        function = getattr(library, "renamex_np", None)
        if function is None:
            raise NotImplementedError("atomic no-replace rename is unavailable")
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        #? RENAME_EXCL = 0x00000004.
        result = function(source_bytes, target_bytes, 4)
    else:
        raise NotImplementedError("atomic no-replace rename is unavailable")
    if result != 0:
        error = ctypes.get_errno()
        if error in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise NotImplementedError(
                "filesystem does not support atomic no-replace rename"
            )
        raise OSError(error, os.strerror(error), str(target))


@contextmanager
def transactional_directory(
    path: str | Path,
) -> Iterator[Path]:
    """Build privately and publish atomically without replacing any target.

    Requires Windows rename, Linux renameat2/RENAME_NOREPLACE, or macOS
    renamex_np/RENAME_EXCL support. Unsupported platforms/filesystems raise
    NotImplementedError and clean staging. Parent directories must be trusted;
    this helper does not anchor their identity against malicious replacement.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=target.parent, prefix=f".{target.name}."))
    try:
        yield staging
        #? Security (VULN-2026-010): reject pre-existing targets, including
        #? symlinks, before publishing the staged directory.
        if target.is_symlink() or target.exists():
            raise FileExistsError(target)
        _rename_directory_noreplace(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


@contextmanager
def advisory_file_lock(
    path: str | Path,
    *,
    timeout: float | None = None,
    shared: bool = False,
    mode: int = 0o600,
) -> Iterator[Path]:
    """Hold an inter-process advisory file lock for the duration of the context.

    Parameters
    ----------
    path : str | Path
        Path of the lock file.
    timeout : float | None, default=None
        Maximum seconds to wait for the lock. If None, blocks indefinitely.
        If timeout <= 0, makes a non-blocking attempt immediately.
        Raises TimeoutError if the lock cannot be acquired within the timeout.
    shared : bool, default=False
        If True, acquires a shared (reader) lock. If False, acquires an exclusive
        (writer) lock.
    mode : int, default=0o600
        File permissions used if the lock file is created.

    Yields
    ------
    Path
        The locked path.

    Raises
    ------
    ValueError
        If the path is empty, a symlink, or timeout is invalid.
    TimeoutError
        If timeout expires before lock acquisition.
    RuntimeError
        If advisory locking is unsupported on the platform.
    """
    if not str(path):
        raise ValueError("lock path must not be empty")
    target = Path(path)
    if target.is_symlink():
        raise ValueError("lock path must not be a symlink")
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout < 0
    ):
        raise ValueError("timeout must be a non-negative finite number or None")
    if not isinstance(shared, bool):
        raise ValueError("shared must be a boolean")
    if (
        isinstance(mode, bool)
        or not isinstance(mode, int)
        or not 0 <= mode <= 0o7777
    ):
        raise ValueError("mode must be an integer between 0 and 0o7777")

    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    descriptor = os.open(target, flags, mode)
    try:
        desc_stat = os.fstat(descriptor)
        path_stat = target.lstat()
        if (
            not stat.S_ISREG(desc_stat.st_mode)
            or not stat.S_ISREG(path_stat.st_mode)
            or not os.path.samestat(desc_stat, path_stat)
        ):
            raise ValueError("lock path must be a non-symlink regular file")

        if os.name == "nt":
            import msvcrt

            windows_runtime = cast(Any, msvcrt)
            if desc_stat.st_size == 0:
                os.write(descriptor, b"\0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            if timeout is None:
                windows_runtime.locking(descriptor, windows_runtime.LK_LOCK, 1)
            else:
                deadline = time.monotonic() + timeout
                delay = 0.005
                while True:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    try:
                        windows_runtime.locking(
                            descriptor, windows_runtime.LK_NBLCK, 1
                        )
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                f"timed out waiting for lock on {target}"
                            ) from None
                        time.sleep(delay)
                        delay = min(delay * 1.5, 0.1)
            try:
                yield target
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                try:
                    windows_runtime.locking(
                        descriptor, windows_runtime.LK_UNLCK, 1
                    )
                except OSError:
                    pass
        else:
            try:
                import fcntl
            except ImportError as exc:
                raise RuntimeError("POSIX fcntl support is unavailable") from exc

            lock_op = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            if timeout is None:
                fcntl.flock(descriptor, lock_op)
            elif timeout == 0:
                try:
                    fcntl.flock(descriptor, lock_op | fcntl.LOCK_NB)
                except OSError as exc:
                    raise TimeoutError(
                        f"timed out waiting for lock on {target}"
                    ) from exc
            else:
                deadline = time.monotonic() + timeout
                delay = 0.005
                while True:
                    try:
                        fcntl.flock(descriptor, lock_op | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                f"timed out waiting for lock on {target}"
                            ) from None
                        time.sleep(delay)
                        delay = min(delay * 1.5, 0.1)
            try:
                yield target
            finally:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
    finally:
        os.close(descriptor)


def _segment_match(
    segment: str,
    pattern_part: str,
) -> bool:
    return fnmatch.fnmatchcase(segment, pattern_part)


def _match_segments_anchored(
    path_parts: tuple[str, ...],
    pattern_parts: tuple[str, ...],
) -> bool:
    """Iterative, polynomial O(N*M) state-set match of pattern_parts to path_parts."""
    if not pattern_parts:
        return not path_parts
    m = len(pattern_parts)

    def closure(
        states: set[int],
    ) -> set[int]:
        stack = list(states)
        expanded = set(states)
        while stack:
            s = stack.pop()
            if s < m and pattern_parts[s] == "**":
                if (s + 1) not in expanded:
                    expanded.add(s + 1)
                    stack.append(s + 1)
        return expanded

    active = closure({0})
    for part in path_parts:
        if not active:
            break
        next_states: set[int] = set()
        for s in active:
            if s < m:
                if pattern_parts[s] == "**":
                    next_states.add(s)
                elif _segment_match(part, pattern_parts[s]):
                    next_states.add(s + 1)
        active = closure(next_states)
    return m in active


def match_path_glob(
    path: str | Path,
    pattern: str,
    *,
    anchored: bool = False,
) -> bool:
    """Match a filesystem path against a glob pattern with ** support.

    Parameters
    ----------
    path : str | Path
        Filesystem path to test.
    pattern : str
        Glob pattern. Segments can contain '*' and '?' wildcards, and '**'
        matches zero or more path segments.
    anchored : bool, default=False
        If True, requires the pattern to match from the beginning of path.
        If False, matches if pattern matches the entire path or any trailing
        suffix (mirroring pathlib.PurePath.match).

    Returns
    -------
    bool
        True if the path matches the pattern.
    """
    if not pattern:
        return False
    normalized = Path(path)
    path_parts = tuple(
        part for part in normalized.parts if part and part != "/"
    )
    pattern_parts = tuple(
        part for part in pattern.replace("\\", "/").split("/") if part
    )
    if not pattern_parts:
        return not path_parts
    if anchored:
        return _match_segments_anchored(path_parts, pattern_parts)
    for start in range(len(path_parts) + 1):
        if _match_segments_anchored(path_parts[start:], pattern_parts):
            return True
    return False


def matches_any_glob(
    path: str | Path,
    patterns: Iterable[str],
    *,
    anchored: bool = False,
) -> bool:
    """Return whether path matches any of the supplied glob patterns.

    Parameters
    ----------
    path : str | Path
        Filesystem path to test.
    patterns : Iterable[str]
        Glob patterns to match against.
    anchored : bool, default=False
        Whether matching must be anchored to the root.

    Returns
    -------
    bool
        True if any pattern matches path.
    """
    for pattern in patterns:
        if pattern and match_path_glob(path, pattern, anchored=anchored):
            return True
    return False


def walk_files(
    root: str | Path,
    *,
    include: Iterable[str] = (),
    exclude: Iterable[str] = (),
    extensions: Iterable[str] = (),
    follow_symlinks: bool = False,
    max_depth: int | None = None,
) -> Iterator[Path]:
    """Deterministically walk directory tree, pruning excluded subtrees early.

    Parameters
    ----------
    root : str | Path
        Root directory to traverse.
    include : Iterable[str], default=()
        Optional glob patterns; if provided, only files matching at least one
        pattern are yielded.
    exclude : Iterable[str], default=()
        Optional glob patterns; matching files or directories are excluded.
        Matching directories are pruned and not descended into.
    extensions : Iterable[str], default=()
        Optional file suffixes (e.g. ('.py', '.json')). If provided, only files
        with matching extensions are yielded.
    follow_symlinks : bool, default=False
        Whether to follow directory symlinks. Default False prevents symlink loops.
    max_depth : int | None, default=None
        Maximum directory descent depth relative to root. None imposes no bound.

    Yields
    ------
    Path
        Matching regular file paths in deterministic sorted order.
    """
    if max_depth is not None and (type(max_depth) is not int or max_depth < 0):
        raise ValueError("max_depth must be a non-negative integer or None")

    base = Path(root).resolve()
    if not base.is_dir():
        raise NotADirectoryError(f"root is not a directory: {base}")

    inc_patterns = tuple(include)
    exc_patterns = tuple(exclude)
    ext_set = tuple(
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in extensions
    )

    visited_dirs: set[tuple[int, int]] = set()

    for current_dir, dir_names, file_names in os.walk(
        base, topdown=True, followlinks=follow_symlinks
    ):
        #? Guard against symlink recursion cycles
        if follow_symlinks:
            try:
                cstat = os.stat(current_dir)
                ckey = (cstat.st_dev, cstat.st_ino)
                if ckey in visited_dirs:
                    dir_names.clear()
                    continue
                visited_dirs.add(ckey)
            except OSError:
                dir_names.clear()
                continue

        #? Enforce max_depth bound
        curr_path = Path(current_dir)
        rel_current = curr_path.relative_to(base)
        current_depth = len(rel_current.parts)
        if max_depth is not None and current_depth >= max_depth:
            dir_names.clear()

        dir_names.sort()
        for d in list(dir_names):
            rel_dir = rel_current / d if current_depth > 0 else Path(d)
            if exc_patterns and matches_any_glob(rel_dir, exc_patterns):
                dir_names.remove(d)

        file_names.sort()
        for f in file_names:
            file_path = curr_path / f
            if not follow_symlinks and file_path.is_symlink():
                continue
            if not file_path.is_file():
                continue
            rel_file = rel_current / f if current_depth > 0 else Path(f)
            if ext_set and not any(f.lower().endswith(ext) for ext in ext_set):
                continue
            if exc_patterns and matches_any_glob(rel_file, exc_patterns):
                continue
            if inc_patterns and not matches_any_glob(rel_file, inc_patterns):
                continue
            yield file_path


def tree_fingerprint(
    root: str | Path,
    *,
    exclude: Iterable[str] = (),
    extensions: Iterable[str] = (),
    algorithm: str = "sha256",
) -> str:
    """Compute a deterministic hash fingerprint of a directory tree.

    Fingerprints relative POSIX paths, file sizes, and nanosecond modification
    timestamps without reading entire file bodies. Suitable for instantaneous
    cache invalidation across builds, lints, or benchmarks.

    Parameters
    ----------
    root : str | Path
        Root directory to fingerprint.
    exclude : Iterable[str], default=()
        Glob patterns for files or subdirectories to omit.
    extensions : Iterable[str], default=()
        Filter for specific file extensions (e.g. ('.py',)).
    algorithm : str, default='sha256'
        Hash algorithm name accepted by hashlib.new.

    Returns
    -------
    str
        Hexadecimal digest string representing directory contents.
    """
    base = Path(root).resolve()
    hasher = hashlib.new(algorithm)
    for file_path in walk_files(
        base,
        exclude=exclude,
        extensions=extensions,
        follow_symlinks=False,
    ):
        rel_posix = file_path.relative_to(base).as_posix()
        try:
            st = file_path.stat()
        except OSError:
            continue
        hasher.update(rel_posix.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(st.st_size.to_bytes(8, "big", signed=False))
        hasher.update(st.st_mtime_ns.to_bytes(8, "big", signed=False))
    return hasher.hexdigest()


__all__ = [
    "advisory_file_lock",
    "atomic_write_bytes",
    "contained_path",
    "lexical_contained_path",
    "match_path_glob",
    "matches_any_glob",
    "transactional_directory",
    "tree_fingerprint",
    "walk_files",
]
