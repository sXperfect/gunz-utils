"""Perpetual security & concurrency audit - PHASE 15 (round-3) regression tests.

Round-3 re-audit of config, env, subprocess, and fs (the deepest deferred/NEW
issues two prior passes missed). Tests are written to FAIL ("red") against the
current source (base b4ca9e9, which already contains the phase 1-14 fixes) and
must pass only after the corresponding production fix lands. Production code is
intentionally not modified.

Findings covered here (NEW, not previously flagged):
1. ``env_overrides`` (config.py:67-70) matches the environment key with a
   hard-coded single-underscore boundary ``prefix_upper + "_"`` regardless of
   the configured ``separator``. For any separator that does not begin with
   ``_`` (e.g. ``::``, ``:``, ``.``) the canonical prefixed key does not start
   with that boundary, so every matching key is silently skipped and the
   function returns ``{}``. The function advertises ``separator`` as a
   configurable parameter and validates it, so a non-underscore separator must
   actually work.
2. ``run_command`` (subprocess.py:395-398) and ``run_command_async``
   (subprocess.py:709-712) validate that ``args`` is a non-empty, non-bare-str
   ``Sequence`` but do not validate that each element is a string. Passing a
   list containing a non-string (e.g. ``[1, 2]``) reaches ``subprocess.Popen``,
   which raises an opaque ``TypeError`` ("expected str, bytes or os.PathLike
   object, not int") from deep inside the subprocess internals instead of a
   clean, early validation error at the documented API boundary.
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
import sys

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.config import env_overrides
from gunz_utils.subprocess import run_command, run_command_async

# -----------------------------------------------------------------------------
# config.py - env_overrides silently drops keys for non-underscore separators
# -----------------------------------------------------------------------------


def test_env_overrides_custom_double_colon_separator_nests() -> None:
    """A ``::`` separator must nest ``MYAPP::A::B`` as ``{'a': {'b': ...}}``.

    The prefix match (config.py:70) uses ``prefix_upper + "_"``, so a key whose
    separator is ``::`` (``MYAPP::A::B``) does not start with the ``_`` boundary
    and is silently skipped, yielding ``{}`` instead of the nested mapping.
    """
    result = env_overrides(
        {"MYAPP::A::B": "x"},
        prefix="MYAPP",
        separator="::",
    )
    assert result == {"a": {"b": "x"}}


def test_env_overrides_custom_dot_separator_nests() -> None:
    """A ``.`` separator must nest ``MYAPP.A.B`` as ``{'a': {'b': ...}}``."""
    result = env_overrides(
        {"MYAPP.A.B": "x"},
        prefix="MYAPP",
        separator=".",
    )
    assert result == {"a": {"b": "x"}}


# -----------------------------------------------------------------------------
# subprocess.py - non-string args are not validated at the API boundary
# -----------------------------------------------------------------------------


def test_run_command_rejects_non_str_args_cleanly() -> None:
    """``run_command`` must reject non-string args with a clean validation error.

    The ``args`` guard (subprocess.py:395-398) rejects a bare string and a
    non-``Sequence``, but does not validate the elements. ``[1, 2]`` reaches
    ``subprocess.Popen``, which raises an opaque ``TypeError`` from deep inside
    the subprocess internals instead of a clear error at the API boundary.
    """
    with pytest.raises(ValueError):
        run_command([1, 2])


def test_run_command_async_rejects_non_str_args_cleanly() -> None:
    """``run_command_async`` must also reject non-string args cleanly."""

    async def attempt() -> None:
        await run_command_async([1, 2])

    with pytest.raises(ValueError):
        asyncio.run(attempt())


# -----------------------------------------------------------------------------
# Sanity green - default/canonical usage still works
# -----------------------------------------------------------------------------


def test_env_overrides_default_separator_still_nests() -> None:
    """Sanity green: the default ``__`` separator still nests correctly."""
    result = env_overrides({"MYAPP__DB__HOST": "x"}, prefix="MYAPP")
    assert result == {"db": {"host": "x"}}


def test_run_command_valid_args_still_works() -> None:
    """Sanity green: valid string args still run and capture output."""
    result = run_command([sys.executable, "-c", "print(42)"])
    assert result.stdout.strip() == "42"
