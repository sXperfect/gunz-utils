# -*- coding: utf-8 -*-
"""
Security utilities.

This module provides helpers for security-related tasks, such as sanitizing inputs.
"""
import re
import os

def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename to prevent path traversal and remove dangerous characters.

    This function ensures that the filename is safe to use in file system operations.
    It:
    1. Removes any path components (directories).
    2. Replaces dangerous characters with a replacement character (default: "_").
    3. Prevents path traversal (e.g., "..").
    4. Limits the length of the filename (255 chars).
    5. Disallows empty filenames.

    Allowed characters: alphanumeric, underscore, dash, dot.

    Parameters
    ----------
    filename : str
        The input filename to sanitize.
    replacement : str, optional
        The character to use for replacing invalid characters (default is "_").

    Returns
    -------
    str
        The sanitized filename.

    Raises
    ------
    ValueError
        If the filename is empty after sanitization.
    """
    # 1. Get base name to avoid directories/path traversal via slashes
    filename = os.path.basename(filename)

    # 2. Replace dangerous characters
    # Keep only alphanumeric, ., -, _
    # Using regex to replace anything that is NOT allowed
    filename = re.sub(r'[^\w\.\-]', replacement, filename)

    # 3. Collapse multiple replacements
    if replacement:
        filename = re.sub(f"{re.escape(replacement)}+", replacement, filename)

    # 4. Strip leading/trailing replacements or dots (dots can be dangerous at start/end)
    filename = filename.strip(replacement + ".")

    # 5. Check empty
    if not filename:
        raise ValueError("Filename is empty after sanitization")

    # 6. Check length (common filesystem limit)
    if len(filename) > 255:
        filename = filename[:255]

    # 7. Check for Windows reserved filenames
    # CON, PRN, AUX, NUL, COM1-9, LPT1-9
    # See: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file#naming-conventions
    # Windows checks the "base" name up to the first dot.
    # e.g. "CON.txt" and "CON.tar.gz" are both invalid.
    # We use split('.')[0] instead of os.path.splitext because splitext only splits the last extension.
    root = filename.split('.')[0]
    if root.upper() in {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }:
        filename = replacement + filename

    return filename
