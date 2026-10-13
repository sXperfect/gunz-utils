"""Phase 23 perpetual audit: round-3 re-audit of ext/validation_stdlib,
ext/validation_pydantic, context, deprecation.

context.py and deprecation.py are clean (deprecation's ``functools.wraps``
preserves coroutine-function detection on async functions; operation_context
token reset is correct). ext/validation_pydantic correctly wraps async
functions in a real ``async def wrapper`` so it remains a coroutine function.

The NEW bug is in ext/validation_stdlib: ``type_checked`` always returns a
synchronous wrapper, even for an ``async def`` target. The synchronous wrapper
validates arguments eagerly (so validation still works), but it is no longer
recognized as a coroutine function — ``asyncio.iscoroutinefunction`` and
``inspect.iscoroutinefunction`` both report ``False``. Any async-aware
dispatcher (FastAPI, pytest-asyncio, aiohttp, custom routers, etc.) that
branches on ``iscoroutinefunction`` will then invoke the wrapped async function
synchronously and receive an unawaited coroutine object, silently breaking
async semantics (and emitting a "coroutine was never awaited" warning). The
pydantic analog returns a true coroutine function for the same input, so this
is a parity/correctness gap.

These tests are expected to be RED against base ``79067b6`` and document the
correct behavior after a fix.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from gunz_utils.ext.validation_stdlib import type_checked


@type_checked
async def _add(x: int, y: int) -> int:
    return x + y


# ---------------------------------------------------------------------------
# ext.validation_stdlib.type_checked breaks coroutine-function detection on an
# async target.
#
# ``type_checked`` (validation_stdlib.py:208-274) always returns a synchronous
# ``wrapper``. For an ``async def`` target the raw function is a coroutine
# function (``iscoroutinefunction`` True), but the wrapped result reports
# ``False``. A dispatcher that checks ``asyncio.iscoroutinefunction`` before
# invoking will call the wrapped async function synchronously, getting back an
# unawaited coroutine object instead of its result.
# ---------------------------------------------------------------------------
def test_type_checked_async_preserves_coroutine_function_detection() -> None:
    assert asyncio.iscoroutinefunction(_add)
    assert inspect.iscoroutinefunction(_add)


# ---------------------------------------------------------------------------
# The wrapped async function must still validate arguments (rejecting a bool
# for an int, in strict parity with the pydantic analog) and return the awaited
# result on success. Validation currently happens eagerly; after a fix the
# async wrapper must preserve both the eager TypeError and the awaited value.
# ---------------------------------------------------------------------------
def test_type_checked_async_still_validates_and_awaits() -> None:
    assert asyncio.run(_add(1, 2)) == 3
    with pytest.raises(TypeError):
        asyncio.run(_add(True, 2))
