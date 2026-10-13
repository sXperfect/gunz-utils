"""Standardized optional Loguru logging integration."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================
from loguru import logger

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================
from .._version import __version__ as __version__

__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "yeremiag@gmail.com"
__license__ = "Clear BSD"

_LOG_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MAX_SESSION_ID_CHARS = 128


def _safe_session_id(
    value: str,
) -> str:
    """Bound and neutralize control characters in log-context text.

    Parameters
    ----------
    value : str
        value parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    if not isinstance(value, str):
        return "GLOBAL"
    safe = "".join(
        character
        if character.isprintable() and character not in "\r\n"
        else "_"
        for character in value[:_MAX_SESSION_ID_CHARS]
    )
    return safe or "GLOBAL"


def _validate_log_name(
    log_name: str,
) -> str:
    """Require a simple filename stem so logs cannot escape logs/.

    Parameters
    ----------
    log_name : str
        log_name parameter.

    Returns
    -------
    str
        The result of the operation.
    """
    if (
        not isinstance(log_name, str)
        or log_name in {".", ".."}
        or _LOG_NAME_RE.fullmatch(log_name) is None
    ):
        raise ValueError(
            "log_name must be a simple filesystem-safe name "
            "(letters, digits, dot, underscore, dash)"
        )
    return log_name


def setup_logging(
    log_name: str,
    verbose: bool = False,
    project_root: Path | None = None,
) -> None:
    """Configure console logging and an optional contained log file.

    Parameters
    ----------
    log_name : str
        log_name parameter.
    verbose : bool
        verbose parameter.
    project_root : Path | None
        project_root parameter.
    """
    log_name = _validate_log_name(log_name)
    logger.remove()
    log_level = "DEBUG" if verbose else "INFO"

    session_id = _safe_session_id(os.environ.get("HH_SESSION_ID", "GLOBAL"))
    logger.configure(extra={"session_id": session_id})

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<magenta>[{extra[session_id]}]</magenta> - <level>{message}</level>"
    )

    logger.add(
        sys.stderr,
        level=log_level,
        format=log_format,
        diagnose=False,
    )

    if project_root is not None:
        root = Path(project_root)
        log_dir = root / "logs"
        if log_dir.is_symlink():
            raise ValueError("log directory must not be a symlink")
        log_dir.mkdir(parents=True, exist_ok=True)
        if log_dir.is_symlink() or not log_dir.is_dir():
            raise ValueError("log directory must be a directory")
        log_path = log_dir / f"{log_name}.log"
        if log_path.is_symlink():
            #? Refuse to follow a symlink planted at the log file path. Writing
            #? through it would append log output into the symlink target (e.g.
            #? a sensitive file outside logs/), defeating the directory guard,
            #? so skip the file sink rather than opening it.
            logger.warning(
                "Refusing to open symlinked log file, skipping file sink: %s",
                log_path,
            )
        else:
            logger.add(
                log_path,
                level="DEBUG",
                format=log_format,
                rotation="10 MB",
                retention="30 days",
                enqueue=True,
                diagnose=False,
            )
