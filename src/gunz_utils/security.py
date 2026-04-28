"""
Security utilities.

This module provides helpers for security-related tasks, such as sanitizing inputs.
"""

# =============================================================================
# METADATA
# =============================================================================
__author__ = "Yeremia Gunawan Adhisantoso"
__email__ = "adhisant@tnt.uni-hannover.de"
__license__ = "Clear BSD"
__version__ = "1.0.0"

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import functools
import os
import re
import typing as t

# Pre-compile the regex for invalid characters (anything not alphanumeric, dot, or dash)
# We use + to collapse multiple invalid characters in one go
_INVALID_CHARS_PATTERN = re.compile(r'[^\w\.\-]+')
_MAX_FILENAME_INPUT_LENGTH = 4096  # Security: limit input size to prevent DoS

@functools.lru_cache(maxsize=16)
def _get_replacement_pattern(replacement: str) -> re.Pattern:
    """Cache compiled patterns for collapsing multiple replacements."""
    return re.compile(f"{re.escape(replacement)}+")

def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    Sanitize a filename to prevent path traversal and remove dangerous characters.

    This function ensures that the filename is safe to use in file system operations.
    It:
    1. Checks input length to prevent DoS.
    2. Removes any path components (directories).
    3. Replaces dangerous characters with a replacement character (default: "_").
    4. Prevents path traversal (e.g., "..").
    5. Limits the length of the filename (255 chars).
    6. Disallows empty filenames.

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
        If the filename is empty after sanitization, if the input is too long,
        or if the replacement string contains path separators.
    """
# 0. Check input length to prevent DoS via excessive string processing
    #? Long inputs can cause regex backtracking, leading to CPU exhaustion
    if len(filename) > _MAX_FILENAME_INPUT_LENGTH:
        raise ValueError(f"Input filename too long (max {_MAX_FILENAME_INPUT_LENGTH} chars)")

    # 1. Check for unsafe replacement characters
    #? We must disallow path separators in the replacement string to prevent
    #? accidental introduction of path traversal or directory creation.
    #? We check for standard separators (/ and \) explicitly to be safe across platforms.
    if "/" in replacement or "\\" in replacement:
        raise ValueError("Replacement string contains path separators")

    # 2. Get base name to avoid directories/path traversal via slashes
    #? os.path.basename strips any directory components, neutralizing ".." attacks
    filename = os.path.basename(filename)

    # 3. Replace dangerous characters
    #? Keep only alphanumeric, ., -, _ using negated character class
    #? The + in the regex collapses multiple invalid chars into one replacement
    filename = _INVALID_CHARS_PATTERN.sub(replacement, filename)

    # 4. Collapse multiple replacements
    if replacement:
        #? Optimization: Only run regex if we actually have consecutive replacements
        #? This avoids unnecessary regex processing for the common case (e.g. "my_file.txt")
        if replacement * 2 in filename:
            #? Use cached pattern for replacement
            pattern = _get_replacement_pattern(replacement)
            filename = pattern.sub(replacement, filename)

    # 5. Strip leading/trailing replacements or dots
    #? Dots at boundaries can be dangerous (e.g., ".hidden" or "file..")
    filename = filename.strip(replacement + ".")

    # 6. Check empty
    if not filename:
        raise ValueError("Filename is empty after sanitization")

    # 7. Check length (common filesystem limit)
    if len(filename) > 255:
        filename = filename[:255]

    # 8. Check for Windows reserved filenames
    #? CON, PRN, AUX, NUL, COM1-9, LPT1-9 are reserved on Windows
    #? See: https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file#naming-conventions
    #? Windows checks the "base" name up to the first dot.
    #? e.g. "CON.txt" and "CON.tar.gz" are both invalid.
    #? We use partition('.')[0] instead of os.path.splitext because splitext only splits the last extension.
    root = filename.partition('.')[0]

    #? Performance Optimization (⚡ Bolt):
    #? Instead of indiscriminately doing .upper() and looking up in a set,
    #? we first check if the length of `root` is 3 or 4, since all reserved names are exactly 3 or 4 chars.
    #? Using `==` with `or` is measurably faster than `in {3, 4}` for simple integer checks.
    root_len = len(root)
    if (root_len == 3 or root_len == 4) and root.upper() in {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }:
        filename = replacement + filename

    return filename


def safe_path_join(base_dir: str, *paths: str) -> str:
    """
    Safely join paths to a base directory, preventing path traversal.

    This function ensures that the resulting path is contained within the
    specified base directory. It resolves '..' components and symbolic links.

    Parameters
    ----------
    base_dir : str
        The base directory to which paths will be joined.
    *paths : str
        The path components to join.

    Returns
    -------
    str
        The absolute, resolved path.

    Raises
    ------
    ValueError
        If the resulting path is outside the base directory.
    """
    # Resolve the base directory to its absolute path
    # Use realpath to resolve symlinks, preventing symlink attacks
    base_path = os.path.realpath(base_dir)

    # Join the paths
    # Note: os.path.join will discard previous components if a component is absolute.
    # We must check for this.
    final_path = base_path
    for p in paths:
        # Prevent null byte injection
        if "\0" in p:
            raise ValueError("Null byte found in path component")

        # Determine if the component is absolute
        # If it is, we treat it as relative to the base (stripping root)
        # OR we just reject it. os.path.join behavior with absolute paths is often a source of bugs.
        # Here we will reject it if it resets the root, OR we can strip the leading slash.
        # Safest is to strip leading slashes/drive letters to force relative join.
        if os.path.isabs(p):
            # Handle Windows drive letters (e.g. C:\) by splitting drive
            # splitdrive returns ('', p) on non-Windows usually, or ('C:', '\path') on Windows
            drive, p = os.path.splitdrive(p)
            # Strip leading separators to ensure it's relative
            p = p.lstrip(os.path.sep)

        final_path = os.path.join(final_path, p)

    # Resolve the final path
    resolved_path = os.path.realpath(final_path)

    # Check if the resolved path starts with the base path
    # We use commonprefix to ensure we don't match partial folder names
    # e.g. /var/www matching /var/www-secret
    if os.path.commonpath([base_path, resolved_path]) != base_path:
         raise ValueError("Path traversal detected: path is outside base directory")

    return resolved_path
