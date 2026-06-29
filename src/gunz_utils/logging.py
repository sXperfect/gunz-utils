# -*- coding: utf-8 -*-
"""
Standardized logging for HyperHedron components.
"""

import os
import sys
from pathlib import Path
from loguru import logger

def setup_logging(
    log_name: str,
    verbose: bool = False,
    project_root: Path | None = None
) -> None:
    """
    Configures standardized logging with session ID tracing.
    """
    logger.remove()
    log_level = "DEBUG" if verbose else "INFO"
    
    # Capture Session ID from environment
    session_id = os.environ.get("HH_SESSION_ID", "GLOBAL")
    
    # Standard format with Session ID
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<magenta>[" + session_id + "]</magenta> - <level>{message}</level>"
    )

    # 1. Console Logger
    logger.add(sys.stderr, level=log_level, format=log_format)

    # 2. File Logger
    if project_root:
        log_dir = project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / f"{log_name}.log",
            level="DEBUG",
            format=log_format,
            rotation="10 MB",
            retention="30 days",
            enqueue=True
        )
