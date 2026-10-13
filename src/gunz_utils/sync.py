"""Shell-free rsync directory mirroring for shared/local caches."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import math
import os
import re
import shutil
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .io import atomic_write
from .subprocess import CommandResult, run_command

_REMOTE_SHELL_SOURCE = re.compile(r"^[^/\\:]+:.+$")
_WINDOWS_DRIVE_SOURCE = re.compile(r"^[A-Za-z]:[\\/].*$")
_FORBIDDEN_EXTRA_OPTIONS = frozenset(
    {
        "-e",
        "-f",
        "-M",
        "--backup-dir",
        "--delete",
        "--files-from",
        "--include-from",
        "--exclude-from",
        "--filter",
        "--log-file",
        "--only-write-batch",
        "--partial-dir",
        "--password-file",
        "--remote-option",
        "--remove-source-files",
        "--rsh",
        "--rsync-path",
        "--temp-dir",
        "--write-batch",
    }
)
_FORBIDDEN_LONG_OPTIONS = frozenset(
    option for option in _FORBIDDEN_EXTRA_OPTIONS if option.startswith("--")
)
#? Complete, non-destructive rsync options that happen to be string-prefixes
#? of a forbidden long option (e.g. "--partial" of "--partial-dir", "--backup"
#? of "--backup-dir"). rsync treats these as the benign option itself rather
#? than as an abbreviation of the forbidden compound, so they must stay
#? allowed. Every other prefix of a forbidden option is an abbreviation and is
#? rejected.
_BENIGN_OPTION_PREFIXES = frozenset({"--partial", "--backup"})


def _unsafe_rsync_extra_argument(
    argument: str,
) -> bool:
    """Reject destructive/execution-affecting options, including abbreviations.

    Parameters
    ----------
    argument : str
        argument parameter.

    Returns
    -------
    bool
        The result of the operation.
    """
    option = argument.split("=", 1)[0]
    if option in {"--include", "--exclude"}:
        #? Literal include/exclude patterns remain supported; a reset can erase
        #? the helper's reserved control-file rules before a later inclusion.
        return argument.partition("=")[2] == "!"
    if argument == "--" or argument.startswith("--delete"):
        return True
    if argument.startswith("-") and not argument.startswith("--"):
        #? Short flags may be clustered. Stop at an argument-taking option so
        #? attached payload letters are not mistaken for additional flags.
        for flag in argument[1:]:
            if flag in "efMT":
                return True
            if flag in "B@":
                break
        return False
    if not option.startswith("--"):
        return option in _FORBIDDEN_EXTRA_OPTIONS
    if option in _FORBIDDEN_LONG_OPTIONS:
        return True
    #? GNU-style long options accept unique abbreviations, so a prefix of a
    #? forbidden option (e.g. "--temp" of "--temp-dir", "--del" of "--delete")
    #? is rejected. The only exception is a prefix that is itself a complete,
    #? benign rsync option (e.g. "--partial", "--backup"), which rsync treats
    #? as that option rather than as an abbreviation.
    if len(option) >= 3 and any(
        forbidden.startswith(option)
        for forbidden in _FORBIDDEN_LONG_OPTIONS
    ):
        return option not in _BENIGN_OPTION_PREFIXES
    return False


@dataclass(frozen=True)
class MirrorResult:
    """Result of one directory mirror operation."""

    source: str
    target: Path
    command: CommandResult
    completion_marker: Path | None


def _normalize_rsync_source(
    source: str | Path,
) -> str:
    """Preserve rsync remote syntax while resolving local paths.

    Parameters
    ----------
    source : str | Path
        source parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    explicit_path = isinstance(source, Path)
    text = str(source)
    if not text:
        raise ValueError("source must not be empty")

    # ? Security (VULN-2026-004): Reject source strings starting with dashes ('-')
    # ? or containing control characters to prevent option/flag injection into rsync.
    if text.startswith("-"):
        raise ValueError("source must not start with a dash")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise ValueError("source contains invalid control characters")

    windows_drive = bool(_WINDOWS_DRIVE_SOURCE.match(text))
    remote = (
        not explicit_path
        and (
            text.startswith("rsync://")
            or (
                not windows_drive
                and bool(_REMOTE_SHELL_SOURCE.match(text))
            )
        )
    )
    if remote:
        #? rsync feeds a remote-shell source to a remote shell (ssh/rsh), so
        #? shell metacharacters there enable remote command injection. Reject
        #? them, consistent with the local-source validation above.
        if re.search(r"[;|&`$<>(){}\[\]*?\"'\\]", text):
            raise ValueError("remote source contains shell metacharacters")
        normalized = text.rstrip("/")
    elif windows_drive:
        normalized = text.replace("\\", "/").rstrip("/")
    else:
        normalized = str(
            Path(text).expanduser().resolve()
        ).rstrip("/")
    return normalized + "/"


@contextmanager
def _advisory_lock(
    path: Path,
) -> Iterator[None]:
    """Hold a POSIX advisory lock for the complete guarded operation.

    Parameters
    ----------
    path : Path
        path parameter.

    Returns
    -------
    Iterator[None]
        The result of the operation.
    """
    try:
        import fcntl
    except ImportError as exc:
        raise RuntimeError(
            "lock=True requires POSIX fcntl support; use lock=False "
            "on unsupported platforms"
        ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("lock path must not be a symlink")

    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(
        path,
        flags,
        0o600,
    )
    with os.fdopen(descriptor, "a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def rsync_mirror(
    source: str | Path,
    target: str | Path,
    *,
    timeout: float | None = 3600.0,
    lock: bool = True,
    completion_marker: str | None = ".gunz-sync-complete",
    extra_args: Sequence[str] = (),
    delete: bool = False,
    max_output_bytes: int | None = 8 * 1024 * 1024,
) -> MirrorResult:
    """Mirror directory contents with rsync and optional advisory locking.

    The advisory lock, when enabled, covers both the rsync process and
    completion-marker publication. This prevents another local process using
    the same helper from observing a success marker while a newer synchronization
    is still running.

    The active root lock and completion-marker names are reserved metadata:
    they are excluded from source payloads and protected from rsync deletion.

    Parameters
    ----------
    source : str | Path
        Local directory or rsync-compatible remote source.
    target : str | Path
        Local destination directory.
    timeout : float | None, optional
        Subprocess timeout in seconds. None disables the timeout.
    lock : bool, optional
        Hold a POSIX advisory lock in the target directory for transfer and
        marker publication. Use False on platforms without fcntl support.
    completion_marker : str | None, optional
        Atomic marker filename written after success. None disables markers.
    extra_args : Sequence[str], optional
        Additional non-destructive rsync arguments inserted before source/target.
        Filter resets and include/exclude-from rule files are rejected to protect
        reserved metadata. Ordinary include/exclude patterns remain supported.
    delete : bool, optional
        Add --delete so destination files absent from source are removed.
        Defaults to False because deletion is destructive.
    max_output_bytes : int | None, optional
        Bound captured stdout/stderr through gunz_utils.subprocess.

    Returns
    -------
    MirrorResult
        Normalized source/target, structured command result, and marker path.

    Raises
    ------
    FileNotFoundError
        If rsync is unavailable.
    RuntimeError
        If locking is requested on a platform without fcntl support.
    ValueError
        If timeout, marker, target, or arguments are invalid.
    CommandError
        If rsync exits unsuccessfully.

    Notes
    -----
    No shell is used. The default rsync flags preserve metadata, allow partial
    transfers, and publish delayed updates. Cross-filesystem and hard-link
    policy is intentionally left to callers through extra_args.
    """
    if timeout is not None and (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or timeout <= 0
    ):
        raise ValueError("timeout must be a finite positive number or None")
    if timeout is not None:
        try:
            timeout_float = float(timeout)
        except OverflowError:
            #? An int too large to convert to float must surface as the
            #? documented ValueError, not leak an internal OverflowError.
            raise ValueError(
                "timeout must be a finite positive number or None"
            ) from None
        if not math.isfinite(timeout_float):
            raise ValueError("timeout must be a finite positive number or None")
    if max_output_bytes is not None and (
        isinstance(max_output_bytes, bool)
        or not isinstance(max_output_bytes, int)
        or max_output_bytes < 0
    ):
        raise ValueError(
            "max_output_bytes must be a non-negative integer or None"
        )
    if completion_marker is not None and (
        not completion_marker
        or "/" in completion_marker
        or "\\" in completion_marker
        or completion_marker in {".", ".."}
    ):
        raise ValueError(
            "completion_marker must be a simple filename or None"
        )
    if isinstance(extra_args, str):
        raise TypeError("extra_args must be a sequence of strings, not a bare str")
    if any(
        not isinstance(argument, str) or not argument
        for argument in extra_args
    ):
        raise ValueError("extra_args must contain non-empty strings")
    unsafe_arguments = [
        argument
        for index, argument in enumerate(extra_args)
        if _unsafe_rsync_extra_argument(argument)
        or (
            argument in {"--include", "--exclude"}
            and index + 1 < len(extra_args)
            and extra_args[index + 1] == "!"
        )
    ]
    if unsafe_arguments:
        raise ValueError(
            "unsafe rsync options are not accepted through extra_args"
        )
    if lock and completion_marker == ".gunz-sync.lock":
        raise ValueError(
            "completion_marker must not reuse the lock filename"
        )
    if shutil.which("rsync") is None:
        raise FileNotFoundError("rsync command not found")
    if not str(target):
        raise ValueError("target must not be empty")

    destination = Path(target).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    source_text = _normalize_rsync_source(source)

    marker = (
        destination / completion_marker
        if completion_marker is not None
        else None
    )
    lock_path = destination / ".gunz-sync.lock"

    rsync_args = [
        "rsync",
        "--archive",
        "--partial",
        "--delay-updates",
    ]
    reserved = [lock_path.name] if lock else []
    if marker is not None:
        reserved.append(marker.name)
    for name in reserved:
        #? Rooted literal rules hide owned metadata on the sender and preserve
        #? its inode on the receiver, before any caller inclusion/exclusion rules.
        pattern = "/" + "".join(
            "\\" + character if character in "*?[]" else character
            for character in name
        )
        rsync_args.extend(["--filter", f"P {pattern}", "--filter", f"H {pattern}"])
    if delete:
        rsync_args.append("--delete")
    rsync_args.extend(extra_args)
    rsync_args.extend(
        [
            "--",
            source_text,
            str(destination),
        ]
    )

    @contextmanager
    def synchronization_scope() -> Iterator[None]:
        """synchronization_scope() function.

        Returns
        -------
        Iterator[None]
            The result of the operation.
        """
        if lock:
            with _advisory_lock(lock_path):
                yield
        else:
            yield

    with synchronization_scope():
        if marker is not None:
            marker.unlink(missing_ok=True)
        try:
            result = run_command(
                rsync_args,
                timeout=timeout,
                check=True,
                max_output_bytes=max_output_bytes,
            )
        except BaseException:
            if marker is not None:
                marker.unlink(missing_ok=True)
            raise

        if marker is not None:
            atomic_write(
                marker,
                "complete\n",
                mkdir=True,
            )

    return MirrorResult(
        source=source_text,
        target=destination,
        command=result,
        completion_marker=marker,
    )


__all__ = ["MirrorResult", "rsync_mirror"]
