"""Perpetual security audit phase 28 (round 4, deepest).

Re-audit of ``collections``, ``dict_utils``, ``signals``, ``sync``, and
``env``.

Findings:

1. ``sync.rsync_mirror`` leaks ``OverflowError`` for an out-of-range integer
   ``timeout`` instead of the documented ``ValueError``.

   sync.py:258-261 validates ``timeout`` with
   ``not math.isfinite(float(timeout))`` but never catches the
   ``OverflowError`` that ``float(timeout)`` raises for an ``int`` too large
   to convert (e.g. ``10**400``).  The surrounding validation is documented to
   reject invalid timeouts with ``ValueError`` (sync.py:242-245), and the
   sibling ``GracefulShutdown.__init__`` (signals.py:250-254) explicitly
   catches ``OverflowError`` and re-raises ``ValueError`` for the exact same
   case.  ``rsync_mirror`` is therefore inconsistent: a huge-int timeout leaks
   an internal ``OverflowError`` instead of the contract's ``ValueError``.

2. ``signals.GracefulShutdown.__aexit__`` silently swallows a cleanup
   callback's ``CancelledError``/``BaseException``.

   signals.py:401-409 drives ``run_cleanup`` through
   ``asyncio.create_task(...)`` and awaits it under ``asyncio.shield`` inside
   ``while not cleanup_task.done(): try: await asyncio.shield(cleanup_task)
   except asyncio.CancelledError: pass``.  That ``except CancelledError: pass``
   is meant to absorb a re-cancellation of the *outer* task so cleanup can
   finish, but it also catches the ``CancelledError`` raised *by the cleanup
   task itself* when a registered callback raises ``CancelledError`` (or any
   other ``BaseException``).  As a result the callback's cancellation is
   silently discarded: it is neither propagated nor retrieved (no warning),
   which contradicts ``run_cleanup``'s documented contract "Cancellation and
   other BaseException signals propagate" (signals.py:350-352).  A caller's
   cleanup callback that is cancelled (e.g. a task awaiting cleanup that gets
   cancelled) has its cancellation lost instead of propagated.
"""

import asyncio

import pytest

from gunz_utils.signals import GracefulShutdown
from gunz_utils.sync import rsync_mirror

# ---------------------------------------------------------------------------
# Finding 1: sync.rsync_mirror timeout validation leaks OverflowError
# ---------------------------------------------------------------------------


def test_rsync_mirror_rejects_huge_int_timeout_with_valueerror():
    """RED: an ``int`` timeout too large for ``float`` (e.g. ``10**400``)
    currently leaks ``OverflowError`` from ``float(timeout)`` inside the
    validation (sync.py:258-261) instead of the documented ``ValueError`` for
    an invalid timeout.  The ``timeout`` check runs before the rsync-binary
    probe, so this does not require rsync to be installed.
    """
    with pytest.raises(ValueError):
        rsync_mirror("source", "target", timeout=10**400, lock=False)


def test_rsync_mirror_rejects_nonfinite_timeout_with_valueerror():
    """GREEN: a non-finite timeout (``inf``) is already rejected as
    ``ValueError`` by the finite check; this pins the correct rejection path
    so the fix only needs to convert the huge-int case to the same error.
    """
    with pytest.raises(ValueError):
        rsync_mirror("source", "target", timeout=float("inf"), lock=False)


# ---------------------------------------------------------------------------
# Finding 2: GracefulShutdown.__aexit__ swallows cleanup cancellation
# ---------------------------------------------------------------------------


def test_graceful_shutdown_aexit_propagates_cleanup_cancellation():
    """RED: a cleanup callback that raises ``asyncio.CancelledError`` is
    silently swallowed by ``GracefulShutdown.__aexit__`` (the
    ``except asyncio.CancelledError: pass`` shield handler at signals.py:405)
    instead of propagating, contradicting ``run_cleanup``'s documented
    "Cancellation ... propagate" contract.  The cancellation must not be lost.
    """
    async def scenario() -> None:
        guard = GracefulShutdown()

        async def callback() -> None:
            raise asyncio.CancelledError("cleanup cancelled")

        guard.add_callback(callback)
        guard.trigger_shutdown()
        with pytest.raises(asyncio.CancelledError):
            await guard.__aexit__(None, None, None)

    asyncio.run(scenario())


def test_graceful_shutdown_run_cleanup_collects_ordinary_exceptions():
    """GREEN: an ordinary ``Exception`` from a cleanup callback is collected
    and returned by ``run_cleanup`` (not raised).  This pins the correct
    handling of ordinary exceptions, distinct from the cancellation case.
    """
    async def scenario() -> None:
        guard = GracefulShutdown()

        def callback() -> None:
            raise RuntimeError("boom")

        guard.add_callback(callback)
        guard.trigger_shutdown()
        errors = await guard.run_cleanup()
        assert len(errors) == 1
        assert isinstance(errors[0][1], RuntimeError)

    asyncio.run(scenario())
