# [ACTIVE]: Add atomic_write utility

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `io`
**Status:** Pending

## 1. Goal

Add an `atomic_write(path, content, mode="w", encoding="utf-8")` utility that writes `content` to `path` via a temp-file-and-`os.replace()` pattern. This guarantees the target path either contains the full old content or the full new content — never a partial write (which happens when a process is killed mid-write or the disk fills up).

This solves a real correctness problem that every "save config / save JSON / dump data" path has. Currently every consumer hand-rolls this and gets it slightly wrong.

## 2. Scope

### In Scope
- New module `src/gunz_utils/io.py` with `atomic_write()` function
- Optional: New directory `src/gunz_utils/ext/` for stdlib-vs-deps variants (not needed for atomic_write — stdlib only)
- Re-export `atomic_write` from `src/gunz_utils/__init__.py` and add to `__all__`
- Tests in `tests/test_core/test_io.py`
- ONE atomic commit with message `feat(io): add atomic_write utility for crash-safe file writes`
- Push to origin/main
- Sync ikarus

### Out of Scope
- Any non-write I/O utilities (read functions, glob helpers, etc.) — separate tasks if needed
- Async file writes — stdlib only for now; async is a future concern
- File locking (fcntl) — atomic_write uses `os.replace()` which is atomic on POSIX and Windows; no locking needed
- Atomic append / atomic move — only atomic_write (create-or-replace) is in scope
- Refactoring existing code to use atomic_write (just add the utility; consumers can adopt later)

## 3. API design

```python
from gunz_utils import atomic_write

# Basic write
atomic_write("/tmp/config.json", '{"key": "value"}')

# Atomic write with binary content
atomic_write("/tmp/data.bin", b"\x00\x01\x02", mode="wb")

# Append mode (atomic replace with new content + append, NOT atomic-append)
# — NOT supported in v1; only create-or-replace semantics

# Custom encoding
atomic_write("/tmp/text.txt", "Hello, 世界", encoding="utf-8")
```

### Signature

```python
def atomic_write(
    path: str | pathlib.Path,
    content: str | bytes,
    *,
    mode: str = "w",
    encoding: str | None = None,
    mkdir: bool = False,
) -> None:
    """Atomically write content to path.

    Writes content to a temp file in the same directory, then uses
    os.replace() to atomically rename the temp file over the target.
    This guarantees readers see either the old content or the new
    content — never a partial write.

    Args:
        path: Target file path. Parent directory must exist unless
            mkdir=True is passed.
        content: String (mode='w' default) or bytes (mode='wb').
        mode: File mode. 'w' for text (default), 'wb' for binary.
        encoding: Text encoding (default 'utf-8' for text mode).
            Ignored in binary mode.
        mkdir: If True, create the parent directory (and parents)
            with mode 0o755 if it doesn't exist.

    Raises:
        OSError: If the write fails or os.replace() fails. The temp
            file is cleaned up before raising.
        ValueError: If content type doesn't match mode (str for 'w',
            bytes for 'wb').
        TypeError: If path is not str or pathlib.Path.
    """
```

### Implementation pattern

```python
import os
import pathlib
import tempfile


def atomic_write(path, content, *, mode="w", encoding=None, mkdir=False):
    path = pathlib.Path(path)
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    elif not path.parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {path.parent}")

    # Validate content type matches mode
    is_binary = "b" in mode
    if is_binary and isinstance(content, str):
        raise ValueError("Binary mode ('wb') requires bytes content")
    if not is_binary and isinstance(content, bytes):
        raise ValueError("Text mode ('w') requires str content")

    # Write to temp file in same directory (required for os.replace atomicity)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        if is_binary:
            with os.fdopen(fd, mode) as f:
                f.write(content)
        else:
            with os.fdopen(fd, mode, encoding=encoding or "utf-8") as f:
                f.write(content)
        # Atomic rename over the target
        os.replace(tmp_path, path)
    except BaseException:
        # Clean up temp file on any failure (including KeyboardInterrupt)
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

## 4. Test plan

`tests/test_core/test_io.py`:

1. **Basic write** — `atomic_write("/tmp/test.txt", "hello")` creates file with correct content
2. **Binary write** — `atomic_write("/tmp/test.bin", b"\x00\x01", mode="wb")` works
3. **Overwrite existing** — writing to an existing file replaces it (no append)
4. **mkdir=True** — creates parent dirs if needed
5. **mkdir=False (default)** — raises `FileNotFoundError` if parent missing
6. **Mode/content mismatch** — `atomic_write("/tmp/x", "text", mode="wb")` raises `ValueError`
7. **Encoding** — `atomic_write("/tmp/x", "Hello, 世界", encoding="utf-8")` writes valid UTF-8
8. **No partial write on failure** — patch `os.replace` to raise; verify temp file is cleaned up and original is unchanged
9. **Custom suffix** — temp file uses `<name>.<random>.tmp` pattern; verify cleanup on success
10. **Path object** — accepts `pathlib.Path` directly

## 5. Verification

After commit:

1. `python -c "from gunz_utils import atomic_write; print(atomic_write)"` — works
2. `python -c "from gunz_utils.io import atomic_write"` — works (direct import)
3. `grep "atomic_write" src/gunz_utils/__init__.py` — listed in `__all__`
4. `pytest tests/test_core/test_io.py -v` — 10 tests pass
5. `pytest tests/ -q` — 96 + 4 (no test count change; this is a NEW test file)
6. `ruff check src/ tests/` — 0 issues

## 6. Definition of Done

- [ ] `src/gunz_utils/io.py` created with `atomic_write()` function
- [ ] `atomic_write` imported in `src/gunz_utils/__init__.py` and added to `__all__`
- [ ] `tests/test_core/test_io.py` created with 10 tests
- [ ] All 6 verification checks pass
- [ ] Commit pushed to `origin/main`
- [ ] ikarus synced to new HEAD
- [ ] Tests pass on ikarus (96 + 4)
- [ ] No other files modified
- [ ] Docstring uses `#?` style comments where the rationale isn't obvious (per python-v6 standards)
- [ ] Module has complete dunder block (`__author__`, `__email__`, `__license__`, `__version__ = "1.6.0"`)