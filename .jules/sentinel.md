## 2025-02-18 - Safe Path Join Implementation
**Vulnerability:** Path Traversal
**Learning:** `os.path.join` is inherently unsafe when handling untrusted input, as it allows `..` and resets the path if an absolute path is encountered.
**Prevention:** Always use a `safe_path_join` utility that resolves the final path (`os.path.realpath`) and verifies it starts with the resolved base directory (`os.path.commonpath`). Strip root/drive components from inputs.
