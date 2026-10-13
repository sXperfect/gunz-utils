"""Phase 30 perpetual audit: round-4 (deepest) re-audit of five core modules.

config.py, redaction.py, and network.py's URI builder were verified correct
across targeted probes (env_overrides nested/prefix/separator/case-collision
handling; merge_configs precedence; redact length-preserving masking +
redact_dict recursion without input mutation; build_network_uri IPv6
bracketing, path/query encoding, and port/scheme/host validation).

One systemic NEW bug class surfaced: unguarded ``float()`` inside the
``math.isfinite(float(...))`` timeout/delay validators of network.py,
resilience.py, and upstream_protocol.py. For a huge integer (e.g. ``10**400``)
the ``float()`` conversion raises ``OverflowError`` *before* the finite-check
can run, leaking an internal ``OverflowError`` instead of the documented
``ValueError``. This is the same recurring unguarded-float defect seen in prior
audit phases; the correct pattern is a type/bool guard first, then ``float()``
inside ``try/except OverflowError -> ValueError``.

Affected sites (verified OverflowError leaks against base ba1690a):
- src/gunz_utils/network.py:223 (tcp_reachable timeout)
- src/gunz_utils/resilience.py:47 (AsyncCircuitBreaker recovery_timeout)
- src/gunz_utils/resilience.py:198 (AsyncBulkhead.run timeout)
- src/gunz_utils/upstream_protocol.py:302 (PolicyUpstream timeout_seconds)
- src/gunz_utils/upstream_protocol.py:328 (PolicyUpstream retry_delay)

This test is expected to be RED against base ``ba1690a`` and documents the
correct behavior after a fix.
"""

from __future__ import annotations

import asyncio

import pytest

from gunz_utils.config import env_overrides, merge_configs
from gunz_utils.network import build_network_uri, tcp_reachable
from gunz_utils.redaction import redact, redact_dict
from gunz_utils.resilience import AsyncBulkhead, AsyncCircuitBreaker
from gunz_utils.upstream_protocol import PolicyUpstream


# ---------------------------------------------------------------------------
# RED: huge-int timeout/delay values must raise ValueError, not leak
# OverflowError, across network/resilience/upstream_protocol.
# ---------------------------------------------------------------------------
def test_network_tcp_reachable_timeout_overflow_is_valueerror() -> None:
    with pytest.raises(ValueError):
        tcp_reachable("example.com", 80, timeout=10**400)


def test_resilience_circuit_breaker_recovery_timeout_overflow_is_valueerror() -> None:
    with pytest.raises(ValueError):
        AsyncCircuitBreaker(recovery_timeout=10**400)
    with pytest.raises(ValueError):
        AsyncCircuitBreaker(recovery_timeout=-(10**400))


def test_resilience_bulkhead_timeout_overflow_is_valueerror() -> None:
    async def op() -> None:
        await asyncio.sleep(0)

    with pytest.raises(ValueError):
        asyncio.run(AsyncBulkhead(1).run(op, timeout=10**400))


def test_upstream_policy_timeout_seconds_overflow_is_valueerror() -> None:
    class Dummy:
        name = "d"

        async def call(self, *a, **k):
            return {}

        async def health_check(self):
            return True

        async def close(self):
            return None

    with pytest.raises(ValueError):
        PolicyUpstream(Dummy(), timeout_seconds=10**400)


def test_upstream_policy_retry_delay_overflow_is_valueerror() -> None:
    class Dummy:
        name = "d"

        async def call(self, *a, **k):
            return {}

        async def health_check(self):
            return True

        async def close(self):
            return None

    with pytest.raises(ValueError):
        PolicyUpstream(Dummy(), retry_delay=10**400)


# ---------------------------------------------------------------------------
# GREEN: config.
# ---------------------------------------------------------------------------
def test_config_env_overrides_and_merge() -> None:
    assert env_overrides({"APP__A__B__C": "1", "APP__X": "2"}, prefix="APP") == {
        "a": {"b": {"c": "1"}},
        "x": "2",
    }
    assert env_overrides({"CFG:A:B": "1"}, prefix="CFG", separator=":") == {
        "a": {"b": "1"}
    }
    # Case-insensitive collision rejected.
    with pytest.raises(ValueError):
        env_overrides({"APP__FOO": "1", "APP__foo": "2"}, prefix="APP")
    # Empty path segment rejected.
    with pytest.raises(ValueError):
        env_overrides({"APP__A__": "1"}, prefix="APP")
    assert merge_configs({"a": {"b": 1}}, {"a": {"c": 2}}) == {"a": {"b": 1, "c": 2}}


# ---------------------------------------------------------------------------
# GREEN: redaction.
# ---------------------------------------------------------------------------
def test_redaction() -> None:
    assert redact("hunter2") == "hu***r2"
    assert redact("hunter2secret", show_chars=4) == "hunt*****cret"
    assert redact("hunter2", show_chars=4) == "****"  # too short -> full mask
    assert redact("hi") == "****"
    assert redact("hunter2", show_chars=0) == "****"
    assert redact(12345) == 12345
    # Length is preserved for long-enough strings.
    out = redact("abcdefghij", show_chars=3)
    assert len(out) == 10
    d = {
        "password": "hunter2",
        "user": "alice",
        "nested": {"token": "abc", "keep": "x"},
        "list": [{"secret_key": "s"}, {"ok": 1}],
    }
    redacted = redact_dict(d)
    assert redacted["password"] == "hu***r2"
    assert redacted["user"] == "alice"
    assert redacted["nested"]["token"] == "****"
    assert redacted["nested"]["keep"] == "x"
    assert redacted["list"][0]["secret_key"] == "****"
    # Input is not mutated.
    assert d["password"] == "hunter2"


# ---------------------------------------------------------------------------
# GREEN: network URI builder.
# ---------------------------------------------------------------------------
def test_network_uri_builder() -> None:
    assert build_network_uri("https", "example.com", port=443) == (
        "https://example.com:443"
    )
    assert build_network_uri("http", "::1", port=80) == "http://[::1]:80"
    assert build_network_uri(
        "https", "example.com", port=443, path="a/b", query={"x": "1"}
    ) == "https://example.com:443/a/b?x=1"
    with pytest.raises(ValueError):
        build_network_uri("", "h")
    with pytest.raises(ValueError):
        build_network_uri("https", "", port=443)
    with pytest.raises(ValueError):
        build_network_uri("https", "h", port=0)
    with pytest.raises(ValueError):
        build_network_uri("https", "h", port=70000)
    with pytest.raises(ValueError):
        build_network_uri("https", "h", port=True)
