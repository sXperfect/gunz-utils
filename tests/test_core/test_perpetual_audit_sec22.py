"""Perpetual security & concurrency audit - PHASE 22 (round-3) regression tests.

Round-3 re-audit of context, deprecation, ext/__init__, validation_stdlib, and
validation_pydantic (the deepest deferred/NEW issues two prior passes missed).
Tests are written to FAIL ("red") against the current source (base 8ee4855,
which already contains the phase 1-21 fixes) and must pass only after the
corresponding production fix lands. Production code is intentionally not
modified.

Findings covered here (NEW, not previously flagged):

1. ``validation_pydantic.type_checked`` (ext/validation_pydantic.py:41-117)
   wraps ``pydantic.validate_call`` inside a synchronous ``try/except
   ValidationError``. For a decorated ASYNC function, ``validate_call`` defers
   validation to await time: ``validated_func(*args, **kw)`` returns a coroutine
   immediately and never raises in the wrapper's ``try``, so the validation
   error surfaces at ``await`` as the RAW ``pydantic.ValidationError`` - the
   value-redaction guarantee (ext/validation_pydantic.py:101-109, "secret-bearing
   validator messages cannot leak") is bypassed and the original input value is
   exposed. The stdlib analog validates synchronously at call time and redacts
   async errors correctly. Expected: async calls must also surface a redacted
   ``TypeError``.

2. ``deprecated`` (deprecation.py:22-80) wraps the target in a SYNCHRONOUS
   ``def wrapped`` even when the target is an ``async def``. After decoration,
   ``asyncio.iscoroutinefunction`` / ``inspect.iscoroutinefunction`` on the
   deprecated function returns ``False``, so async consumers that dispatch on
   coroutine-function-ness (e.g. ``if iscoroutinefunction(fn): await fn()``)
   treat the deprecated async function as a plain callable and break. The
   decorator claims to "preserve its signature metadata" but drops the
   coroutine property. Expected: a deprecated async function must remain
   recognizable as a coroutine function.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import asyncio
import warnings

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.deprecation import GunzDeprecationWarning, deprecated

# -----------------------------------------------------------------------------
# validation_pydantic.py - async functions bypass the error-redaction wrapper
# -----------------------------------------------------------------------------


def test_validation_pydantic_async_redacts_error() -> None:
    """RED: an async validated function must raise a redacted TypeError."""
    pytest.importorskip("pydantic")
    from gunz_utils.ext.validation_pydantic import type_checked

    @type_checked
    async def af(x: int) -> int:
        return x

    with pytest.raises(TypeError) as excinfo:
        asyncio.run(af("supersecretvalue"))
    assert "supersecretvalue" not in str(excinfo.value)


def test_validation_pydantic_sync_redacts_error() -> None:
    """Sanity green: a sync validated function already raises a redacted TypeError."""
    pytest.importorskip("pydantic")
    from gunz_utils.ext.validation_pydantic import type_checked

    @type_checked
    def sf(x: int) -> int:
        return x

    with pytest.raises(TypeError) as excinfo:
        sf("supersecretvalue")
    assert "supersecretvalue" not in str(excinfo.value)


# -----------------------------------------------------------------------------
# deprecation.py - deprecated async functions lose their coroutine identity
# -----------------------------------------------------------------------------


def test_deprecated_async_preserves_coroutine_function() -> None:
    """RED: a deprecated async function must stay a recognized coroutine function."""
    @deprecated("use new_api")
    async def af(x: int) -> int:
        return x

    assert asyncio.iscoroutinefunction(af)


def test_deprecated_async_still_awaitable() -> None:
    """RED: a deprecated async function must still be awaitable and return its value."""
    @deprecated("use new_api")
    async def af(x: int) -> int:
        return x

    assert asyncio.run(af(42)) == 42


def test_deprecated_sync_warns_and_calls() -> None:
    """Sanity green: a deprecated sync function warns and still returns its value."""
    @deprecated("use new_api")
    def sf(x: int) -> int:
        return x * 2

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = sf(21)

    assert result == 42
    assert any(issubclass(item.category, GunzDeprecationWarning) for item in caught)
