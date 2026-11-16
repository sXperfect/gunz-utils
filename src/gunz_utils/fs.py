"""Production-safe filesystem helpers."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import contextlib
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
from .hashing import SUPPORTED_ALGOS
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
    if "\x00" in str(path) or "\x00" in str(root):
        raise ValueError("paths must not contain NUL bytes")
    supplied = Path(path)
    if supplied.is_absolute() or supplied.drive or supplied.root:
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

    target = Path(path)
    if target.is_symlink():
        raise ValueError("lock path must not be a symlink")

    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    try:
        descriptor = os.open(target, flags, mode)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError("lock path must not be a symlink") from exc
        raise
    if os.name == "posix":
        with contextlib.suppress(OSError):
            os.fchmod(descriptor, mode)
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
                        now = time.monotonic()
                        if now >= deadline:
                            raise TimeoutError(
                                f"timed out waiting for lock on {target}"
                            ) from None
                        time.sleep(min(delay, max(0.0, deadline - now)))
                        delay = min(delay * 1.5, 0.1)
            try:
                yield target
            finally:
                os.lseek(descriptor, 0, os.SEEK_SET)
                with contextlib.suppress(OSError):
                    windows_runtime.locking(
                        descriptor, windows_runtime.LK_UNLCK, 1
                    )
        else:
            try:
                import fcntl
            except ImportError as exc:
                raise RuntimeError("POSIX fcntl support is unavailable") from exc

            contention_errnos = {
                errno.EACCES,
                errno.EAGAIN,
                getattr(errno, "EWOULDBLOCK", errno.EAGAIN),
            }
            lock_op = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
            if timeout is None:
                fcntl.flock(descriptor, lock_op)
            elif timeout == 0:
                try:
                    fcntl.flock(descriptor, lock_op | fcntl.LOCK_NB)
                except OSError as exc:
                    if exc.errno in contention_errnos:
                        raise TimeoutError(
                            f"timed out waiting for lock on {target}"
                        ) from exc
                    raise
            else:
                deadline = time.monotonic() + timeout
                delay = 0.005
                while True:
                    try:
                        fcntl.flock(descriptor, lock_op | fcntl.LOCK_NB)
                        break
                    except OSError as exc:
                        if exc.errno not in contention_errnos:
                            raise
                        now = time.monotonic()
                        if now >= deadline:
                            raise TimeoutError(
                                f"timed out waiting for lock on {target}"
                            ) from None
                        time.sleep(min(delay, max(0.0, deadline - now)))
                        delay = min(delay * 1.5, 0.1)
            try:
                yield target
            finally:
                with contextlib.suppress(OSError):
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
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


def _match_path_parts(
    path_parts: tuple[str, ...],
    pattern: str,
    anchored: bool = False,
) -> bool:
    if not pattern:
        return False
    pattern_parts = tuple(
        part for part in pattern.replace("\\", "/").split("/") if part
    )
    if not pattern_parts:
        return not path_parts
    if (
        pattern_parts[-1] != "**"
        and "*" not in pattern_parts[-1]
        and "?" not in pattern_parts[-1]
    ):
        if not path_parts or path_parts[-1] != pattern_parts[-1]:
            return False
    if anchored:
        if (
            pattern_parts[0] != "**"
            and "*" not in pattern_parts[0]
            and "?" not in pattern_parts[0]
        ):
            if not path_parts or path_parts[0] != pattern_parts[0]:
                return False
        return _match_segments_anchored(path_parts, pattern_parts)
    for start in range(len(path_parts) + 1):
        if _match_segments_anchored(path_parts[start:], pattern_parts):
            return True
    return False


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
    return _match_path_parts(path_parts, pattern, anchored=anchored)


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
    if isinstance(patterns, (str, bytes, bytearray)):
        raise TypeError(
            f"patterns must be an iterable of pattern "
                f"strings, not {type(patterns).__name__}"
        )
    normalized = Path(path)
    path_parts = tuple(
        part for part in normalized.parts if part and part != "/"
    )
    for pattern in patterns:
        if pattern and _match_path_parts(path_parts, pattern, anchored=anchored):
            return True
    return False


def _walk_files_iter(
    base: Path,
    inc_patterns: tuple[str, ...],
    exc_patterns: tuple[str, ...],
    ext_set: tuple[str, ...],
    follow_symlinks: bool,
    max_depth: int | None,
) -> Iterator[Path]:
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
        dir_names[:] = [
    d for d in dir_names if not (
        exc_patterns and matches_any_glob(
            rel_current /
            d if current_depth > 0 else Path(d),
             exc_patterns)) ]

        file_names.sort()
        for f in file_names:
            file_path = curr_path / f
            if not follow_symlinks:
                try:
                    lst = os.lstat(file_path)
                    if stat.S_ISLNK(lst.st_mode) or not stat.S_ISREG(lst.st_mode):
                        continue
                except OSError:
                    continue
            else:
                try:
                    st = os.stat(file_path)
                    if not stat.S_ISREG(st.st_mode):
                        continue
                except OSError:
                    continue
            rel_file = rel_current / f if current_depth > 0 else Path(f)
            if ext_set and not any(f.lower().endswith(ext) for ext in ext_set):
                continue
            if exc_patterns and matches_any_glob(rel_file, exc_patterns):
                continue
            if inc_patterns and not matches_any_glob(rel_file, inc_patterns):
                continue
            yield file_path


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
    if not isinstance(follow_symlinks, bool):
        raise TypeError("follow_symlinks must be bool")
    if max_depth is not None and (type(max_depth) is not int or max_depth < 0):
        raise ValueError("max_depth must be a non-negative integer or None")
    if isinstance(include, (str, bytes, bytearray)):
        raise TypeError(
            f"include must be an iterable of patterns, not {type(include).__name__}"
        )
    if isinstance(exclude, (str, bytes, bytearray)):
        raise TypeError(
            f"exclude must be an iterable of patterns, not {type(exclude).__name__}"
        )
    if isinstance(extensions, (str, bytes, bytearray)):
        raise TypeError(
            f"extensions must be an iterable of "
                f"extensions, not {type(extensions).__name__}"
        )

    base = Path(root).resolve()
    if not base.is_dir():
        raise NotADirectoryError(f"root is not a directory: {base}")

    inc_patterns = tuple(include)
    exc_patterns = tuple(exclude)
    ext_set = tuple(
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in extensions
    )

    return _walk_files_iter(
        base,
        inc_patterns,
        exc_patterns,
        ext_set,
        follow_symlinks,
        max_depth,
    )


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
        Hash algorithm name in :data:`gunz_utils.hashing.SUPPORTED_ALGOS`.

    Returns
    -------
    str
        Hexadecimal digest string representing directory contents.
    """
    if isinstance(exclude, (str, bytes, bytearray)):
        raise TypeError(
            f"exclude must be an iterable of patterns, not {type(exclude).__name__}"
        )
    if isinstance(extensions, (str, bytes, bytearray)):
        raise TypeError(
            f"extensions must be an iterable of "
                f"extensions, not {type(extensions).__name__}"
        )
    if algorithm not in SUPPORTED_ALGOS:
        allowed = sorted(SUPPORTED_ALGOS)
        raise ValueError(
            f"unsupported algorithm {algorithm!r}; expected one of {allowed}"
        )
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
            st = file_path.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            continue
        rel_bytes = rel_posix.encode("utf-8")
        hasher.update(len(rel_bytes).to_bytes(8, "big", signed=False))
        hasher.update(rel_bytes)
        hasher.update(b"\x00")
        hasher.update(stat.S_IMODE(st.st_mode).to_bytes(4, "big", signed=False))
        hasher.update(st.st_size.to_bytes(8, "big", signed=False))
        hasher.update(st.st_mtime_ns.to_bytes(8, "big", signed=True))
    return hasher.hexdigest()


def ensure_dir(
    path: str | Path,
    *,
    mode: int = 0o755,
) -> Path:
    """Create directory hierarchy safely, rejecting symlinks at the target path.

    Parameters
    ----------
    path : str | Path
        Directory path to ensure.
    mode : int, default=0o755
        Permissions mode for created directories.

    Returns
    -------
    Path
        Resolved created directory path.

    Raises
    ------
    ValueError
        If the target path is a symlink.
    NotADirectoryError
        If an existing path is not a directory.
    """
    target = Path(path)
    if target.is_symlink():
        raise ValueError(f"target path {target} is a symlink")
    if target.exists() and not target.is_dir():
        raise NotADirectoryError(f"target path exists and is not a directory: {target}")
    target.mkdir(mode=mode, parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError(f"target path {target} resolved to a symlink")
    return target


ensure_directory = ensure_dir


def is_file_locked(
    path: str | Path,
) -> bool:
    """Test whether a file currently has an active advisory lock."""
    target = Path(path)
    if not target.exists():
        return False
    try:
        with advisory_file_lock(target, timeout=0.0):
            return False
    except (TimeoutError, OSError):
        return True


def safe_remove(
    path: str | Path,
) -> bool:
    """Safely remove a file if it exists. Returns True if deleted, False if missing."""
    target = Path(path)
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False


def safe_rmtree(
    path: str | Path,
    *,
    missing_ok: bool = True,
) -> bool:
    """Safely remove a directory tree. Returns True if deleted, False if missing."""
    target = Path(path)
    if not target.exists():
        if missing_ok:
            return False
        raise FileNotFoundError(f"directory not found: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"not a directory: {target}")
    shutil.rmtree(target)
    return True


def file_size_bytes(
    path: str | Path,
) -> int:
    """Return the size of a regular file in bytes."""
    target = Path(path)
    return target.stat().st_size


def touch_file(
    path: str | Path,
    *,
    mode: int = 0o644,
) -> Path:
    """Create an empty file if not present or update its timestamps."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.touch(mode=mode, exist_ok=True)
    else:
        now = time.time()
        os.utime(target, (now, now))
    return target


def copy_file_atomic(
    source: str | Path,
    destination: str | Path,
) -> Path:
    """Copy a file atomically via a temporary file in the destination directory."""
    src = Path(source)
    dst = Path(destination)
    if not src.is_file():
        raise FileNotFoundError(f"source file not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    temp_dst = dst.parent / f".tmp_{dst.name}_{os.getpid()}_{time.time_ns()}"
    try:
        shutil.copy2(src, temp_dst)
        os.replace(temp_dst, dst)
    except Exception:
        if temp_dst.exists():
            temp_dst.unlink(missing_ok=True)
        raise
    return dst


def get_disk_usage(
    path: str | Path,
) -> tuple[int, int, int]:
    """Return (total, used, free) disk space in bytes for the path mount."""
    usage = shutil.disk_usage(path)
    return (usage.total, usage.used, usage.free)


def walk_directory(
    base_dir: str | Path,
    pattern: str = "*",
    *,
    recursive: bool = True,
    max_depth: int | None = None,
) -> Iterator[Path]:
    """Walk files and directories matching pattern with optional depth bounds."""
    depth = max_depth if recursive else (1 if max_depth is None else min(max_depth, 1))
    return walk_files(
    base_dir,
    include=(
        pattern,
        ) if pattern != "*" else (),
         max_depth=depth)


def find_files(
    base_dir: str | Path,
    *,
    pattern: str = "*",
    min_size: int | None = None,
    max_size: int | None = None,
    extensions: tuple[str, ...] | None = None,
) -> Iterator[Path]:
    """Find files satisfying pattern, extension, and byte size bounds."""
    if min_size is not None and (isinstance(min_size, bool) or min_size < 0):
        raise ValueError("min_size must be a non-negative integer")
    if max_size is not None and (isinstance(max_size, bool) or max_size < 0):
        raise ValueError("max_size must be a non-negative integer")
    if min_size is not None and max_size is not None and min_size > max_size:
        raise ValueError("min_size cannot exceed max_size")

    ext_iter = extensions if extensions is not None else ()
    for p in walk_files(
    base_dir,
    include=(
        pattern,
        ) if pattern != "*" else (),
         extensions=ext_iter):
        sz = p.stat().st_size
        if min_size is not None and sz < min_size:
            continue
        if max_size is not None and sz > max_size:
            continue
        yield p


class TemporaryDirectoryPool:
    """Manages a pool of reusable temporary directories."""

    def __init__(self,
        prefix: str = "tmp_pool_",
        max_dirs: int = 10,
    ) -> None:
        if isinstance(max_dirs, bool) or not isinstance(max_dirs, int) or max_dirs < 1:
            raise ValueError("max_dirs must be an integer >= 1")
        self.prefix = prefix
        self.max_dirs = max_dirs
        self._pool: list[Path] = []
        self._all_created: list[Path] = []

    @contextmanager
    def acquire(self) -> Iterator[Path]:
        """Acquire a temporary directory from the pool and return it on exit."""
        if self._pool:
            d = self._pool.pop()
        else:
            d = Path(tempfile.mkdtemp(prefix=self.prefix))
            self._all_created.append(d)
        d.mkdir(parents=True, exist_ok=True)
        try:
            yield d
        finally:
            for item in d.iterdir():
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
            if len(self._pool) < self.max_dirs:
                self._pool.append(d)
            else:
                shutil.rmtree(d, ignore_errors=True)
                if d in self._all_created:
                    self._all_created.remove(d)

    def cleanup(self) -> None:
        """Remove all created temporary directories in this pool."""
        self._pool.clear()
        for d in self._all_created:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        self._all_created.clear()

    def __enter__(self) -> TemporaryDirectoryPool:
        return self

    def __exit__(self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        self.cleanup()


__all__ = [
    "TemporaryDirectoryPool",
    "advisory_file_lock",
    "atomic_write_bytes",
    "contained_path",
    "copy_file_atomic",
    "ensure_dir",
    "ensure_directory",
    "file_size_bytes",
    "find_files",
    "get_disk_usage",
    "is_file_locked",
    "lexical_contained_path",
    "match_path_glob",
    "matches_any_glob",
    "safe_remove",
    "safe_rmtree",
    "touch_file",
    "transactional_directory",
    "tree_fingerprint",
    "walk_directory",
    "walk_files",
]
