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

    return filename
