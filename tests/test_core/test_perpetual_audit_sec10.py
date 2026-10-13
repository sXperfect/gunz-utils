"""Perpetual security & concurrency audit - PHASE 10 (round-2) regression tests.

Round-2 re-audit of subprocess, fs, network, provenance_graph, serialization,
and ext/secure_store. Tests are written to FAIL ("red") against the current
source (base 24fdab6, which already contains the phase 1-9 fixes) and must pass
only after the corresponding production fix lands. Production code is
intentionally not modified.

Findings covered here (NEW, not previously flagged):
1. ``run_command``/``run_command_async`` (subprocess.py:358, :660) accept a bare
   ``str`` as ``args``. Only ``if not args`` is validated (:395/:705), so a
   non-empty string passes and is silently mis-tokenized by ``list(args)``
   (subprocess.py:280, :402) into single-character commands - ``run_command(
   "echo hi")`` tries to exec the command ``"e"`` instead of ``echo hi``. The
   API requires a sequence; a bare string must be rejected with a clear
   TypeError/ValueError rather than misinterpreted.
2. ``SecureStore.audit_events`` (secure_store.py:1803) does not enforce the
   locked-store invariant. Every other metadata/read method (``list_keys``,
   ``get``, ``get_bytes``, ``set``, ``delete``, ``verify_integrity``) raises
   ``RuntimeError`` when ``_fernet is None``, but ``audit_events`` returns all
   audit rows - including ``secret_name`` - on a locked store, leaking audit
   metadata to an unauthenticated caller who has database file access.
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import asyncio
import tempfile

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.ext.secure_store import SecureStore
from gunz_utils.subprocess import run_command, run_command_async


def _fresh_store() -> SecureStore:
    directory = tempfile.mkdtemp()
    store = SecureStore(base_dir=directory)
    store.unlock()
    return store


# -----------------------------------------------------------------------------
# subprocess.py - bare-string args silently mis-tokenized
# -----------------------------------------------------------------------------


def test_run_command_rejects_bare_string_args() -> None:
    """A bare ``str`` ``args`` must be rejected, not mis-tokenized into chars.

    ``run_command`` validates only ``if not args`` (subprocess.py:395), so a
    non-empty string passes and is split per-character by ``list(args)``
    (subprocess.py:402). ``run_command("echo hi")`` then attempts to exec the
    command ``"e"`` (FileNotFoundError) instead of ``echo hi``. The sequence
    API must reject a bare string with a clear TypeError/ValueError.
    """
    with pytest.raises((TypeError, ValueError)):
        run_command("echo hi")


def test_run_command_async_rejects_bare_string_args() -> None:
    """``run_command_async`` must also reject a bare ``str`` ``args``.

    Same defect on the async path (subprocess.py:705, :717-718), where a bare
    string is unpacked per-character into ``create_subprocess_exec``.
    """
    async def attempt() -> None:
        await run_command_async("echo hi")

    with pytest.raises((TypeError, ValueError)):
        asyncio.run(attempt())


# -----------------------------------------------------------------------------
# ext/secure_store.py - audit_events bypasses the locked-store invariant
# -----------------------------------------------------------------------------


def test_secure_store_audit_events_requires_unlock() -> None:
    """``audit_events`` must refuse to return rows on a locked store.

    After ``lock()`` every other read/write method raises ``RuntimeError``, but
    ``audit_events`` (secure_store.py:1803) reads the audit table with no locked
    check, leaking audit metadata (including ``secret_name``) to a caller who
    has database file access but not the key.
    """
    store = _fresh_store()
    try:
        store.set("api_token", "secret-value")
        store.set("db_pass", "hunter2")
        store.lock()
        assert not store.is_unlocked()
        with pytest.raises(RuntimeError, match="locked"):
            store.audit_events()
    finally:
        store.close()


# -----------------------------------------------------------------------------
# Sanity green - correct usage still works
# -----------------------------------------------------------------------------


def test_run_command_sequence_args_still_works() -> None:
    """Sanity green: a proper sequence of arguments runs correctly."""
    result = run_command(["echo", "hi"])
    assert result.returncode == 0
    assert result.stdout.strip() == "hi"


def test_secure_store_audit_events_works_when_unlocked() -> None:
    """Sanity green: audit events are returned while the store is unlocked."""
    store = _fresh_store()
    try:
        store.set("k", "v")
        events = store.audit_events()
        assert any(event["secret_name"] == "k" for event in events)
    finally:
        store.close()
