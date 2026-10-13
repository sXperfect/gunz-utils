"""Perpetual security & concurrency audit - PHASE 18 (round-3) regression tests.

Round-3 re-audit of upstream_protocol, redaction, secure_store (ext), and
formatting (the deepest deferred/NEW issues two prior passes missed). Tests are
written to FAIL ("red") against the current source (base 5296336, which already
contains the phase 1-17 fixes) and must pass only after the corresponding
production fix lands. Production code is intentionally not modified.

Findings covered here (NEW, not previously flagged):
1. ``PolicyUpstream.call`` (upstream_protocol.py:379-385) retries only
   ``UpstreamUnavailableError``, never ``TimeoutError``. For an idempotent tool
   with ``max_attempts > 1`` - the exact configuration meant to make transient
   failures safe to retry - a single timeout raises ``UpstreamTimeoutError``
   after the first attempt and is never retried, while an ``Unavailable`` error
   is retried up to ``max_attempts``. A timeout is the canonical transient
   upstream failure, so the idempotent-retry policy silently fails to protect
   against it.
2. ``redact_dict`` (redaction.py:195-245) walks nested structures with an
   unbounded recursive ``_walk``. A pathologically deep dict/list/tuple
   (e.g. deeper than the interpreter recursion limit) raises ``RecursionError``
   instead of a clean, bounded error. The primary use case for ``redact_dict``
   is masking arbitrary (potentially untrusted) config before logging, so
   unbounded recursion on hostile deep input is a robustness/DoS defect.
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

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.redaction import redact_dict
from gunz_utils.upstream_protocol import (
    PolicyUpstream,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

# -----------------------------------------------------------------------------
# upstream_protocol.py - PolicyUpstream.call does not retry timeouts
# -----------------------------------------------------------------------------


class _CountingClient:
    """Minimal UpstreamClient that always times out or reports unavailable."""

    name = "test"

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.calls = 0

    async def call(self, tool_name: str, arguments: dict) -> dict:
        self.calls += 1
        if self.mode == "timeout":
            await asyncio.sleep(10)
        raise UpstreamUnavailableError("down", upstream=self.name)

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def test_policy_upstream_retries_timeout_for_idempotent_tool() -> None:
    """An idempotent tool must be retried on timeout when max_attempts > 1.

    ``PolicyUpstream.call`` (upstream_protocol.py:379-385) catches only
    ``UpstreamUnavailableError`` for retry; ``TimeoutError`` immediately raises
    ``UpstreamTimeoutError``. So a transient timeout on an idempotent call is
    attempted exactly once and never retried, defeating the idempotent-retry
    configuration.
    """

    async def scenario() -> int:
        client = _CountingClient("timeout")
        policy = PolicyUpstream(
            client,
            timeout_seconds=0.05,
            max_attempts=3,
            idempotent_tools=frozenset({"get"}),
            retry_delay=0,
        )
        try:
            await policy.call("get", {})
        except UpstreamTimeoutError:
            pass
        return client.calls

    assert asyncio.run(scenario()) >= 2


# -----------------------------------------------------------------------------
# redaction.py - redact_dict unbounded recursion on deep input
# -----------------------------------------------------------------------------


def test_redact_dict_deeply_nested_no_recursion_error() -> None:
    """``redact_dict`` must handle deep nesting without RecursionError.

    The recursive ``_walk`` (redaction.py:195-245) has no depth bound, so a
    structure nested deeper than the interpreter recursion limit raises
    ``RecursionError`` instead of returning a masked copy. Callers mask
    arbitrary (potentially untrusted) config before logging, so this must be
    bounded.
    """
    depth = sys.getrecursionlimit() + 200
    root: dict = {}
    current = root
    for _index in range(depth):
        current["x"] = {}
        current = current["x"]
    current["password"] = "hunter2"

    result = redact_dict(root)
    assert result is not None


# -----------------------------------------------------------------------------
# Sanity green - reference behavior that must keep working
# -----------------------------------------------------------------------------


def test_policy_upstream_retries_unavailable_for_idempotent_tool() -> None:
    """Sanity green: an Unavailable error is retried up to max_attempts."""

    async def scenario() -> int:
        client = _CountingClient("unavailable")
        policy = PolicyUpstream(
            client,
            timeout_seconds=5,
            max_attempts=3,
            idempotent_tools=frozenset({"get"}),
            retry_delay=0,
        )
        try:
            await policy.call("get", {})
        except UpstreamUnavailableError:
            pass
        return client.calls

    assert asyncio.run(scenario()) == 3


def test_redact_dict_normal_nested_still_masked() -> None:
    """Sanity green: ordinary nested dicts/lists still mask secret leaves."""
    result = redact_dict({"config": {"db": {"password": "hunter2", "host": "h"}}})
    assert "hunter2" not in result["config"]["db"]["password"]
    assert result["config"]["db"]["host"] == "h"
