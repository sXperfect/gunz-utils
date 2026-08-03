# [ACTIVE]: Add safe_parsers module (safe_int, safe_float, safe_bool, parse_bool)

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `parsing`
**Status:** Pending

## 1. Goal

Add robust string→primitive parsers: `safe_int`, `safe_float`, `safe_bool`, `parse_bool`. Used in every CLI argument parser, environment variable loader, and config file reader. Currently every consumer hand-rolls these with subtle bugs (e.g., `int("  42  ")` raises, `int("3.14")` raises, `bool("False")` returns `True`).

## 2. Scope

### In Scope
- New module `src/gunz_utils/parsing.py` with 4 functions:
  - `safe_int(value, default=None, *, min=None, max=None, base=10)` — int parsing with bounds
  - `safe_float(value, default=None, *, min=None, max=None, allow_inf=True, allow_nan=False)` — float parsing with bounds and inf/nan control
  - `safe_bool(value, default=None)` — lenient bool parsing (string + int forms), returns default on unrecognized
  - `parse_bool(value)` — strict bool parsing (only recognizes canonical forms), raises on unrecognized
- Re-export all 4 from `src/gunz_utils/__init__.py` and add to `__all__`
- Tests in `tests/test_core/test_parsing.py`
- ONE atomic commit with message `feat(parsing): add safe_int, safe_float, safe_bool, parse_bool utilities`
- Push to origin/main
- Sync ikarus

### Out of Scope
- Date/time parsing (use `datetime.fromisoformat`)
- Path parsing (use `pathlib.Path`)
- Enum parsing (`BaseStrEnum` already handles that)
- Custom error types (use built-in `ValueError`)

## 3. API design

```python
from gunz_utils import safe_int, safe_float, safe_bool, parse_bool

# Integer parsing with bounds
safe_int("42")                    # 42
safe_int("  42  ")                # 42 (whitespace stripped)
safe_int("3.14")                  # None (default) — float string doesn't coerce
safe_int("abc")                   # None (default) — invalid
safe_int("abc", default=0)        # 0
safe_int("100", min=0, max=50)    # None — out of range
safe_int("100", min=0, max=200)   # 100

# Float parsing with bounds
safe_float("3.14")                # 3.14
safe_float("inf")                 # float('inf')  (allow_inf=True default)
safe_float("nan", allow_nan=True) # float('nan')  (must explicitly opt-in)
safe_float("abc")                 # None (default)

# Lenient bool — accepts many forms, returns default on unrecognized
safe_bool("yes")                  # True
safe_bool("no")                   # False
safe_bool("1")                    # True
safe_bool("0")                    # False
safe_bool("true")                 # True
safe_bool("False")                # False
safe_bool("y")                    # True
safe_bool("n")                    # False
safe_bool("on")                   # True
safe_bool("off")                  # False
safe_bool("maybe")                # None (default; unrecognized)
safe_bool("maybe", default=False) # False

# Strict bool — only canonical forms, raises on unrecognized
parse_bool("true")                # True
parse_bool("false")               # False
parse_bool("maybe")               # raises ValueError
```

### Implementations

```python
# parsing.py
import math
import re

__all__ = ["safe_int", "safe_float", "safe_bool", "parse_bool"]

# Whitespace-trimmed value for use in all parsers
def _stripped(v):
    if isinstance(v, str):
        return v.strip()
    return v

def safe_int(value, default=None, *, min=None, max=None, base=10):
    """Parse int from string. Returns default on failure."""
    try:
        result = int(_stripped(value), base)
    except (ValueError, TypeError):
        return default
    if min is not None and result < min:
        return default
    if max is not None and result > max:
        return default
    return result

def safe_float(value, default=None, *, min=None, max=None, allow_inf=True, allow_nan=False):
    """Parse float from string. Returns default on failure."""
    try:
        result = float(_stripped(value))
    except (ValueError, TypeError):
        return default
    if not allow_inf and math.isinf(result):
        return default
    if not allow_nan and math.isnan(result):
        return default
    if min is not None and result < min:
        return default
    if max is not None and result > max:
        return default
    return result

_TRUE_STRINGS = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_STRINGS = frozenset({"0", "false", "f", "no", "n", "off"})

def safe_bool(value, default=None):
    """Lenient bool parsing. Returns default on unrecognized input."""
    if isinstance(value, bool):
        return value
    s = _stripped(value)
    if not isinstance(s, str):
        return default
    low = s.lower()
    if low in _TRUE_STRINGS:
        return True
    if low in _FALSE_STRINGS:
        return False
    return default

def parse_bool(value):
    """Strict bool parsing. Raises ValueError on unrecognized input."""
    if isinstance(value, bool):
        return value
    s = _stripped(value)
    if not isinstance(s, str):
        raise ValueError(f"Cannot parse bool from {value!r}")
    low = s.lower()
    if low in _TRUE_STRINGS:
        return True
    if low in _FALSE_STRINGS:
        return False
    raise ValueError(f"Cannot parse bool from {value!r}; expected one of {sorted(_TRUE_STRINGS | _FALSE_STRINGS)}")
```

## 4. Test plan

`tests/test_core/test_parsing.py`:

For each of 4 functions, ~8 tests = 32 total:
- Valid inputs return expected values
- Whitespace is stripped
- Invalid inputs return `default` (or raise for `parse_bool`)
- Bounds are enforced (`min`, `max`)
- Type mismatches return `default` (or raise)
- For booleans: int forms (0/1), string forms (yes/no/true/false/on/off/t/f/y/n), case-insensitive
- For booleans: `parse_bool` raises `ValueError` on unrecognized; `safe_bool` returns default

## 5. Verification

After commit:

1. `python -c "from gunz_utils import safe_int, safe_float, safe_bool, parse_bool; print('OK')"` — works
2. `pytest tests/test_core/test_parsing.py -v` — 32 tests pass
3. `pytest tests/ -q` — 96 + 4 (no count change in core; new test file)
4. `ruff check src/ tests/` — 0 issues

## 6. Definition of Done

- [ ] `src/gunz_utils/parsing.py` created with 4 functions
- [ ] All 4 functions imported in `src/gunz_utils/__init__.py` and added to `__all__`
- [ ] `tests/test_core/test_parsing.py` created with 32 tests
- [ ] All verification checks pass
- [ ] Commit pushed to `origin/main`
- [ ] ikarus synced
- [ ] Module has complete dunder block + `#?` comments for non-obvious design choices
- [ ] No other files modified