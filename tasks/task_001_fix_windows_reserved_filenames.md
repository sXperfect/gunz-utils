# Task: Fix Windows Reserved Filenames Vulnerability

## Description
This task involved identifying and mitigating a security vulnerability related to Windows reserved filenames in the `sanitize_filename` utility.

Filenames such as `CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, and `LPT1-9` are reserved by the Windows operating system for device drivers. If a user uploads a file with one of these names (even with an extension, e.g., `CON.txt`), attempting to interact with it on a Windows server or client could lead to:
- Denial of Service (application hangs).
- Unexpected file system behavior (writing to a device instead of a file).
- Errors preventing file deletion or access.

The fix involved modifying `src/gunz_utils/security.py` to detect these reserved names (case-insensitive) and prepend a replacement character (default `_`) to neutralize them.

## Implementation Details
- **File:** `src/gunz_utils/security.py`
- **Method:** `sanitize_filename`
- **Logic:**
  1. Extract the base filename up to the first dot (e.g., `CON` from `CON.tar.gz`).
  2. Check if the upper-case base name exists in the set of reserved Windows names.
  3. If reserved, prepend the `replacement` character to the original filename.

## Lessons Learned
1. **Cross-Platform Awareness:** Even if the application runs on Linux containers (like this environment), generated files might be downloaded to or processed on Windows systems. Security sanitization must consider the "lowest common denominator" of file system constraints.
2. **Windows Filename Parsing:** Windows treats `CON.txt`, `con.tar.gz`, and `CON` all as the device `CON`. Simply checking `os.path.splitext` is insufficient because it only splits the *last* extension. The check must apply to the substring *before the first dot*.
3. **Implicit Dependencies:** When modifying utility functions, be mindful of new dependencies. I initially considered `os.path.splitext` but switched to `str.split` to avoid potential missing imports and to better match Windows' behavior regarding "base" names.

## Future Improvements & Development Guidelines
1. **Prioritization:**
   - **Security First:** Edge cases that can cause DoS or IO errors should be prioritized, especially those involving user input (filenames, paths).
   - **Defensive Coding:** assume input is malicious or malformed.

2. **Constraints:**
   - **Performance:** Sanitization runs on every file operation; keep checks efficient (e.g., set lookups).
   - **Compatibility:** Maintain behavior for valid filenames while strictly filtering invalid ones.

3. **Recommendations:**
   - Continue to audit for other file system restrictions (e.g., max path length, which is already handled, or other reserved characters like `:` on Windows/Mac).
   - Add fuzz testing for `sanitize_filename` to discover other edge cases.
