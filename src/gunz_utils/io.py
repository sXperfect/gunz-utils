"""Crash-safe file writing utilities for the Gunz ecosystem."""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import os
import pathlib
import tempfile

__author__ = "Yeremia Gunz"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "BSD 3-Clause"
__version__ = "1.6.0"

__all__ = ["atomic_write"]


def atomic_write(
    path: str | pathlib.Path,
    content: str | bytes,
    *,
    mode: str = "w",
    encoding: str | None = None,
    mkdir: bool = False,
) -> None:
    """Atomically write content to path.

    Writes content to a temp file in the same directory, then uses
    ``os.replace()`` to atomically rename the temp file over the target.
    This guarantees readers see either the old content or the new content,
    never a partial write.

    Parameters
    ----------
    path : str or pathlib.Path
        Target file path. Parent directory must exist unless ``mkdir=True``.
    content : str or bytes
        String content in text mode or bytes content in binary mode.
    mode : str, default="w"
        File mode. Use ``"w"`` for text or ``"wb"`` for binary content.
    encoding : str or None, default=None
        Text encoding, defaulting to UTF-8. Ignored in binary mode.
    mkdir : bool, default=False
        Create missing parent directories with mode ``0o755`` when true.

    Returns
    -------
    None
        The content is written to ``path`` in place.

    Raises
    ------
    TypeError
        If ``path`` is not a string or ``pathlib.Path``.
    ValueError
        If content type does not match the selected mode.
    OSError
        If directory creation, writing, replacement, or cleanup fails.
    """
    if not isinstance(path, (str, pathlib.Path)):
        raise TypeError("path must be str or pathlib.Path")

    target = pathlib.Path(path)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    elif not target.parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {target.parent}")

    is_binary = "b" in mode
    if is_binary and isinstance(content, str):
        raise ValueError("Binary mode ('wb') requires bytes content")
    if not is_binary and isinstance(content, bytes):
        raise ValueError("Text mode ('w') requires str content")

    #? A same-directory descriptor keeps os.replace atomic across filesystems.
    fd, tmp_path = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    try:
        if is_binary:
            with os.fdopen(fd, mode) as file:
                file.write(content)
        else:
            with os.fdopen(fd, mode, encoding=encoding or "utf-8") as file:
                file.write(content)
        os.replace(tmp_path, target)
    except BaseException:
        #? Cleanup catches BaseException so interrupts cannot leave temp files.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
