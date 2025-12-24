# Task: Prevent Information Leakage in Validation Errors

**Date:** 2025-12-24

## Description
This task addressed a security vulnerability where `pydantic` validation errors wrapped by the `type_checked` decorator would leak the raw input value in the exception message. This poses a risk if sensitive data (like passwords or API keys) is passed to a function and fails validation, potentially exposing the secret in logs or error responses.

## Changes
- Modified `src/gunz_utils/validation.py`:
  - Updated the error message formatting in the `type_checked` decorator.
  - Replaced `{input_val!r}` with `type(input_val).__name__`.
  - The error message now reports "got type 'str'" instead of "got 'secret_value'".
- Created `tests/test_validation_leak.py`:
  - Added a test case that deliberately passes a sensitive string to an integer argument.
  - Verifies that the sensitive string is **not** present in the raised `TypeError` message.
  - Verifies that the type information **is** present.

## Lessons Learned
- **Information Leakage:** Exception messages are a common vector for information leakage. Developers often include input values for debugging convenience, but this is dangerous for sensitive fields.
- **Defense in Depth:** Even if inputs should be valid, validation layers must fail securely.
- **Pydantic Internals:** `pydantic`'s `ValidationError` object contains the raw input. When re-packaging this error, one must be careful not to blindly forward the raw input.

## Future Improvements
- Consider adding a configuration option to `type_checked` to allow logging raw values in non-production environments (e.g., `debug=True`), but keep the default secure.
- Audit other exception raisers in the codebase for similar leaks.
