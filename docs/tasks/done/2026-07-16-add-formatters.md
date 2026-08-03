# [ACTIVE]: Add format_bytes, format_duration, format_count utilities

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `formatting`
**Status:** Pending

## 1. Goal

Add 3 human-readable formatters: `format_bytes(n)`, `format_duration(seconds)`, `format_count(n)`. Used in every log line that reports a file size, elapsed time, or count. Currently every consumer hand-rolls these with slightly different conventions.

## 2. Scope

### In Scope
- New module `src/gunz_utils/formatting.py` with 3 functions:
  - `format_bytes(n, precision=1, binary=False)` — human-readable file size
  - `format_duration(seconds, precision=1)` — human-readable elapsed time
  - `format_count(n, precision=1)` — human-readable large numbers (1000 → 1K, 1500000 → 1.5M)
- Re-export all 3 from `src/gunz_utils/__init__.py` and add to `__all__`
- Tests in `tests/test_core/test_formatting.py`
- ONE atomic commit with message `feat(formatting): add format_bytes, format_duration, format_count utilities`
- Push to origin/main
- Sync ikarus

### Out of Scope
- Locale-aware formatting (no i18n support — uses hardcoded English units)
- Custom unit systems (e.g., `format_bytes` with binary=False uses SI units: KB/MB/GB at powers of 10; binary=True uses IEC: KiB/MiB/GiB at powers of 2)
- Date/time formatting (use `datetime.isoformat` or `arrow`)
- Pretty-printing structured data (use `pprint` or `json.dumps(..., indent=2)`)

## 3. API design

```python
from gunz_utils import format_bytes, format_duration, format_count

# Bytes — SI units by default (KB = 1000 B), IEC units with binary=True (KiB = 1024 B)
format_bytes(0)                  # "0 B"
format_bytes(512)                # "512 B"
format_bytes(1024)               # "1.0 KB"   (precision=1)
format_bytes(1536)               # "1.5 KB"
format_bytes(1024 * 1024)        # "1.0 MB"
format_bytes(1024 * 1024 * 1024) # "1.0 GB"
format_bytes(2**40)              # "1.0 TB"
format_bytes(1536, precision=2)  # "1.50 KB"
format_bytes(1024, binary=True)  # "1.0 KiB"
format_bytes(2**30, binary=True) # "1.0 GiB"

# Duration — adaptive precision
format_duration(0)               # "0s"
format_duration(0.5)             # "500ms"
format_duration(30)              # "30.0s"
format_duration(90)              # "1m 30s"
format_duration(3661)            # "1h 1m 1s"
format_duration(86400)           # "1d 0h 0m"
format_duration(90061)           # "1d 1h 1m 1s"
format_duration(45.6)            # "45.6s"

# Count — K/M/B/T suffixes (SI)
format_count(0)                  # "0"
format_count(999)                # "999"
format_count(1000)               # "1.0K"
format_count(1500)               # "1.5K"
format_count(1_000_000)          # "1.0M"
format_count(1_234_567)          # "1.2M"
format_count(1_000_000_000)      # "1.0B"
format_count(1234, precision=0)  # "1K"
```

### Implementations

```python
# formatting.py

__all__ = ["format_bytes", "format_duration", "format_count"]

def format_bytes(n, *, precision=1, binary=False):
    """Format byte count as human-readable string.

    SI units (default): B, KB, MB, GB, TB (powers of 10)
    IEC units (binary=True): B, KiB, MiB, GiB, TiB (powers of 2)
    """
    n = float(n)
    if n < 0:
        return f"-{format_bytes(-n, precision=precision, binary=binary)}"
    base = 1024 if binary else 1000
    suffixes = ["B", "KiB", "MiB", "GiB", "TiB"] if binary else ["B", "KB", "MB", "GB", "TB"]
    if n < base:
        return f"{int(n)} {suffixes[0]}"
    for i, suffix in enumerate(suffixes[1:], start=1):
        n /= base
        if n < base:
            return f"{n:.{precision}f} {suffix}"
    return f"{n:.{precision}f} {suffixes[-1]}"

def format_duration(seconds, *, precision=1):
    """Format elapsed seconds as human-readable string."""
    seconds = float(seconds)
    if seconds < 0:
        return f"-{format_duration(-seconds, precision=precision)}"
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{seconds:.{precision}f}s"
    minutes, s = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {s}s"
    hours, m = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {m}m {s}s"
    days, h = divmod(hours, 24)
    return f"{days}d {h}h {m}m {s}s"

def format_count(n, *, precision=1):
    """Format large integer count with K/M/B/T suffix."""
    n = int(n)
    if abs(n) < 1000:
        return str(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    for suffix in ["K", "M", "B", "T"]:
        n /= 1000
        if n < 1000:
            return f"{sign}{n:.{precision}f}{suffix}"
    return f"{sign}{n:.{precision}f}T"  # Peta-scale if needed
```

## 4. Test plan

`tests/test_core/test_formatting.py` — ~25 tests:

For `format_bytes`:
- 0, 512, 1024, 1536, 1048576, 1073741824, 1099511627776
- Precision=0, 1, 2
- Binary mode (KiB, MiB, etc.)
- Negative numbers

For `format_duration`:
- 0, 0.5, 30, 90, 3661, 86400, 90061
- Precision=0, 1
- Negative numbers

For `format_count`:
- 0, 999, 1000, 1500, 1_000_000, 1_000_000_000, 1_234_567
- Precision=0, 1
- Negative numbers

## 5. Verification

After commit:

1. `python -c "from gunz_utils import format_bytes, format_duration, format_count; print('OK')"` — works
2. `pytest tests/test_core/test_formatting.py -v` — ~25 tests pass
3. `pytest tests/ -q` — 96 + 4 (no count change in core; new test file)
4. `ruff check src/ tests/` — 0 issues

## 6. Definition of Done

- [ ] `src/gunz_utils/formatting.py` created with 3 functions
- [ ] All 3 functions imported in `src/gunz_utils/__init__.py` and added to `__all__`
- [ ] `tests/test_core/test_formatting.py` created with ~25 tests
- [ ] All verification checks pass
- [ ] Commit pushed to `origin/main`
- [ ] ikarus synced
- [ ] Module has complete dunder block + `#?` comments for non-obvious design choices
- [ ] No other files modified