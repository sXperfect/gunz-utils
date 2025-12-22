# Task: Add `safe_path_join` Security Utility

## Description
Implemented a `safe_path_join` function in `src/gunz_utils/security.py` to securely join a base directory with one or more path components.

This utility prevents:
1.  **Path Traversal**: Prevents users from accessing files outside the base directory using `..`.
2.  **Absolute Path Injection**: Neutralizes absolute paths in input (which `os.path.join` would normally treat as a reset) by stripping root components.
3.  **Symlink Attacks**: Uses `os.path.realpath` to resolve symlinks, ensuring the *actual* file location is within the base directory.
4.  **Null Byte Injection**: Checks for and rejects null bytes in inputs.

## Lessons Learned
-   **`os.path.join` Dangers**: Relying solely on `os.path.join` is insufficient for security.
-   **Symlink Resolution**: Security checks must resolve symlinks (`os.path.realpath`) to avoid jailbreaks via symlinks.
-   **Cross-Platform Testing**: Path tests must use `tmp_path` and `os.path` helpers to be robust across Linux, Windows, and macOS (symlinks).

## Future Improvements
-   Extend `sanitize_filename` to optionally restrict to ASCII-only characters to prevent homoglyph attacks.
