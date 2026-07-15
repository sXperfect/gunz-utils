# 2025-02-18 - DoS Protection in Enum Utilities

**Task:** Prevent Denial of Service (DoS) attacks via excessive string processing in `BaseStrEnum` and `BaseIntEnum`.
**Solution:** Added a strict input length limit (1024 characters) to `from_fuzzy_string` and `from_fuzzy_int_string` methods.
**Learnings:** Standard library enums or custom extensions often lack input validation, making them vulnerable to resource exhaustion when exposed to untrusted input.
**Future Improvements:** Consider making the limit configurable via environment variables if needed.
