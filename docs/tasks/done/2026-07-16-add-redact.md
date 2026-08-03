# [ACTIVE]: Add redact utility for secret masking

**Date:** 2026-07-16
**Role:** Programmer
**Component:** `security`
**Status:** Pending

## 1. Goal

Add a `redact(value, patterns=None)` utility that masks secret values (API keys, tokens, passwords) when logging or displaying. Prevents accidental credential leakage in log files, error messages, debug dumps, and screenshots.

## 2. Scope

### In Scope
- New module `src/gunz_utils/redaction.py` with:
  - `redact(value, patterns=None)` function — mask a single value
  - `redact_dict(d, patterns=None)` function — walk a dict and mask values whose keys match pattern names
  - Built-in default patterns covering common secret key names
- Re-export from `src/gunz_utils/__init__.py` and add to `__all__`
- Tests in `tests/test_core/test_redaction.py`
- ONE atomic commit with message `feat(security): add redact and redact_dict utilities for secret masking`
- Push to origin/main
- Sync ikarus

### Out of Scope
- Cryptographic redaction (HMAC-based constant-time masking) — overkill for log output
- PII detection (SSN, credit card, email regex) — different problem space, would be a separate utility
- Log-handler integration (auto-redact on every log call) — could be a future wrapper, but `redact_dict` covers the main use case
- Configurable redaction strategies (full mask, partial mask, hash) — start with simple "show first/last 4 chars" + "full mask" and add if needed

## 3. API design

```python
from gunz_utils import redact, redact_dict

# Default patterns (covers common secret key names)
SECRET_PATTERNS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_key", "secret_key", "auth", "authorization", "credential",
    "credentials", "private_key", "session_token", "refresh_token",
})

# Redact a single value (string)
redact("sk-1234567890abcdef")                    # "sk-1****cdef"
redact("hunter2")                                # "h****2"
redact("short")                                  # "****"  (too short to partially mask)

# Redact a dict (recursive)
config = {
    "host": "api.example.com",
    "port": 443,
    "username": "alice",
    "password": "hunter2",
    "auth": {"token": "abc123xyz", "expires": 1234567890},
    "checks": [{"name": "db", "password": "secret123"}],
}
redact_dict(config)
# {
#     "host": "api.example.com",
#     "port": 443,
#     "username": "alice",
#     "password": "h****2",  # partial mask
#     "auth": {"token": "a****xyz", "expires": 1234567890},
#     "checks": [{"name": "db", "password": "s****t123"}],  # recursive
# }

# Custom patterns
redact_dict(config, patterns={"api_key"})  # only mask keys named "api_key"
```

### Implementation

```python
# redaction.py

import re

__all__ = ["redact", "redact_dict", "SECRET_PATTERNS"]

# Default patterns — case-insensitive substring match against dict keys
SECRET_PATTERNS = frozenset({
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "access_key", "secret_key", "auth", "authorization", "credential",
    "credentials", "private_key", "session_token", "refresh_token",
})

_MASK = "****"

def redact(value, *, show_chars=2):
    """Mask a string value, showing first/last `show_chars` characters.

    Strings shorter than 2*show_chars+1 are fully masked.

    Args:
        value: The string to mask. Non-strings are returned as-is.
        show_chars: Number of chars to show on each end.

    Examples:
        >>> redact("hunter2")
        'h****2'
        >>> redact("hunter2", show_chars=4)
        'hunte****er2'
        >>> redact("hi")
        '****'
    """
    if not isinstance(value, str):
        return value
    if len(value) <= 2 * show_chars:
        return _MASK
    return f"{value[:show_chars]}{_MASK}{value[-show_chars:]}"

def _is_secret_key(key, patterns):
    """Case-insensitive substring match: does `key` contain any pattern?"""
    if not isinstance(key, str):
        return False
    key_lower = key.lower()
    return any(p in key_lower for p in patterns)

def redact_dict(d, *, patterns=None, show_chars=2):
    """Recursively mask values whose keys match secret patterns.

    Walks dicts and lists. Non-dict/list values are returned as-is.
    Strings whose key matches a pattern (case-insensitive substring) are masked.
    """
    if patterns is None:
        patterns = SECRET_PATTERNS
    if isinstance(d, dict):
        return {
            k: redact(v, show_chars=show_chars) if _is_secret_key(k, patterns) else redact_dict(v, patterns=patterns, show_chars=show_chars)
            for k, v in d.items()
        }
    if isinstance(d, list):
        return [redact_dict(item, patterns=patterns, show_chars=show_chars) for item in d]
    return d
```

## 4. Test plan

`tests/test_core/test_redaction.py` — ~20 tests:

For `redact`:
- Long string → first/last N chars + mask
- Short string (≤ 2N chars) → full mask
- Empty string → empty string
- show_chars=0 → all mask
- show_chars=1, 2, 4
- Non-string (int, None, dict, list) → returned as-is

For `redact_dict`:
- Top-level secret keys masked
- Nested dict secrets masked
- List of dicts secrets masked
- Non-secret keys untouched
- Mixed case keys (e.g., "Password", "API_KEY") are detected
- Custom patterns work
- Non-dict input returned as-is (passthrough)
- Empty dict → empty dict

For `SECRET_PATTERNS`:
- Contains expected common names

## 5. Verification

After commit:

1. `python -c "from gunz_utils import redact, redact_dict, SECRET_PATTERNS; print('OK')"` — works
2. `pytest tests/test_core/test_redaction.py -v` — 20 tests pass
3. `pytest tests/ -q` — 96 + 4 (no count change in core; new test file)
4. `ruff check src/ tests/` — 0 issues

## 6. Definition of Done

- [ ] `src/gunz_utils/redaction.py` created with `redact`, `redact_dict`, `SECRET_PATTERNS`
- [ ] All 3 names imported in `src/gunz_utils/__init__.py` and added to `__all__`
- [ ] `tests/test_core/test_redaction.py` created with ~20 tests
- [ ] All verification checks pass
- [ ] Commit pushed to `origin/main`
- [ ] ikarus synced
- [ ] Module has complete dunder block + `#?` comments for non-obvious design choices (e.g., why case-insensitive substring match, why partial mask vs hash)
- [ ] No other files modified