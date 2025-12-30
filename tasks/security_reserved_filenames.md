# Task: Security Hardening - Windows Reserved Filenames

## Description
Identified and fixed a security vulnerability in `sanitize_filename` where Windows reserved filenames (e.g., "CON", "NUL") were not properly sanitized if the user provided an empty `replacement` string. This could lead to creation of reserved files on Windows systems, potentially causing Denial of Service or file system errors.

## Changes
- Modified `sanitize_filename` in `src/gunz_utils/security.py` to enforce a fallback prefix (defaulting to `_`) when a reserved filename is detected and the `replacement` string is empty.
- Added comprehensive unit tests in `tests/test_security_reserved.py` to verify protection against all common reserved filenames with various replacement strings (empty, valid).
- Documented the vulnerability and prevention pattern in `.jules/sentinel.md`.

## Lessons Learned
- **Input Sanitization Fallbacks:** When a security check relies on modifying user input (e.g. prepending a string), always assume the user-provided modification parameters might be ineffective (e.g. empty strings). Hardcode safe fallbacks for critical security boundaries.
- **Reserved Filenames:** Windows reserved filenames are case-insensitive and apply regardless of extension. Validation must check the base name.

## Future Improvements
- Consider adding a strict mode to `sanitize_filename` that raises an error for reserved names instead of sanitizing them, giving the caller more control.
