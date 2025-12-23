## 2025-02-18 - Safe Path Join Implementation
**Vulnerability:** Path Traversal
**Learning:** `os.path.join` is inherently unsafe when handling untrusted input, as it allows `..` and resets the path if an absolute path is encountered.
**Prevention:** Always use a `safe_path_join` utility that resolves the final path (`os.path.realpath`) and verifies it starts with the resolved base directory (`os.path.commonpath`). Strip root/drive components from inputs.
## 2025-02-18 - [Information Leakage in Exceptions]
**Vulnerability:** Path Traversal exception message in `safe_path_join` leaked the internal base directory and resolved path.
**Learning:** Developers often include variable values in exceptions for debugging, but for security-critical functions like path validation, this can expose sensitive server structure (Information Disclosure CWE-209).
**Prevention:** Use generic error messages for security violations (e.g. "Path traversal detected") or log details to a secure internal log instead of the exception message that might bubble up to the user.
