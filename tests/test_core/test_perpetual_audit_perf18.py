"""Phase 18 perpetual audit: round-3 re-audit of timing/versioning/identifiers/
partitions.

Focused on the deepest corner a prior pass could miss: reusing a ``Timer`` as a
context manager does not restart timing, so a second ``with`` block reports the
stale elapsed value from the first block instead of its own duration.

This test is expected to be RED against base ``5296336`` and documents the
correct behavior after a fix.
"""

from __future__ import annotations

import time

from gunz_utils.timing import Timer


# ---------------------------------------------------------------------------
# timing.Timer as a context manager does not restart on re-entry.
#
# ``Timer.__enter__`` only starts the clock when ``_start_time`` is ``None``
# (timing.py:83-87). A ``Timer`` that has already been used (auto-started and
# then stopped by a first ``with`` block) keeps its old ``_start_time`` and
# ``_end_time``, so entering it a second time is a no-op: ``elapsed`` reports
# the frozen value from the first block, not the second block's duration. This
# is inconsistent with ``start()``'s documented "Start or restart" semantics
# (timing.py:47-54) and silently yields wrong timing for any reused context
# manager.
# ---------------------------------------------------------------------------
def test_timer_context_manager_restarts_on_reentry() -> None:
    timer = Timer()

    with timer:
        time.sleep(0.05)
    first = timer.elapsed
    assert first >= 0.04

    with timer:  # re-enter the same context manager
        time.sleep(0.15)
    second = timer.elapsed

    # The second block's elapsed must reflect the second block's duration, not
    # the stale value from the first block.
    assert second >= 0.10, (
        f"expected second block elapsed >= 0.10 (it slept 0.15s), got {second:.4f} "
        f"(stale first value {first:.4f} leaked through; Timer did not restart)"
    )
