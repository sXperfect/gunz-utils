"""Perpetual security audit phase 35 (round 4, deepest).

Re-audit of ``upstream_protocol``, ``redaction``, ``resilience``, ``network``,
and ``env``.

Findings (all NEW, not fixed in phases 1-34):

1. ``network._is_non_public_address`` fails to classify the RFC 7343 ORCHIDv2
   special-use range ``2001:20::/28`` (second hextet 0x20..0x2f) as non-public
   (network.py:182-196).  These addresses are overlay-only and not globally
   routed, but Python reports ``is_global=True`` and none of the checked flags
   catch them, so ``_is_non_public_address("2001:20::1")`` returns ``False``.
   An external-only probe policy would therefore permit connecting to a
   non-routable special-use range.  Correct behavior: reject the ORCHIDv2
   range explicitly (``2001:20::/28`` per RFC 7343 -- not ``/27``, which would
   wrongly also cover the adjacent ``2001:30::/28`` block).

2. ``PolicyUpstream.call`` reuses the caller's mutable ``arguments`` dict
   verbatim on every retry attempt (upstream_protocol.py:387-418).  An
   idempotent-tool retry after a timeout or ``UpstreamUnavailableError``
   passes the *same* dict object to ``_client.call``, so a client that
   consumes or mutates its ``arguments`` (a routine pattern for a mutable
   dict argument) changes what the retry sees, and the caller's own dict is
   mutated as a side effect.  Correct behavior: re-issue each retry with a
   shallow copy of ``arguments`` so retries are semantically identical and
   the caller's input is untouched.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: IPv4/IPv6 private/special classification that already works,
ORCHID-free special ranges, retry counting and idempotency gating, bulkhead
and circuit-breaker invariants, redaction coverage and mask determinism, and
env parsing/bounds/error typing.
"""

import asyncio

import pytest

from gunz_utils import redaction, resilience
from gunz_utils.env import env as env_fn
from gunz_utils.env import env_bool
from gunz_utils.network import _is_non_public_address
from gunz_utils.upstream_protocol import PolicyUpstream, UpstreamUnavailableError

# ---------------------------------------------------------------------------
# Finding 1: ORCHIDv2 (RFC 7343, 2001:20::/28) must be non-public
# ---------------------------------------------------------------------------


def test_orchidv2_special_use_is_non_public():
    """RED: the RFC 7343 ORCHIDv2 range ``2001:20::/28`` is overlay-only and
    not globally routed, so it must be classified non-public under an
    external-only policy.  Currently Python reports ``is_global=True`` and the
    helper returns ``False`` (it would probe a non-routable special-use range).
    """
    assert _is_non_public_address("2001:20::1") is True


def test_orchidv2_upper_boundary_is_non_public():
    """RED: RFC 7343 ORCHIDv2 is ``2001:20::/28`` (second hextet 0x20..0x2f);
    the upper edge must also be classified non-public.
    """
    assert _is_non_public_address("2001:2f:ffff:ffff:ffff:ffff:ffff:ffff") is True


# ---------------------------------------------------------------------------
# Finding 2: PolicyUpstream retries must re-issue identical (copied) arguments
# ---------------------------------------------------------------------------


def test_retry_reissues_identical_arguments():
    """RED: when an idempotent tool's first attempt fails and the client
    consumes one of its ``arguments``, the retry must still receive the
    original arguments (and the caller's dict must not be mutated).  Currently
    the wrapper passes the same mutable dict on every attempt, so the retry
    sees the consumed dict and the caller's input is clobbered.
    """
    recorded: list[dict[str, object]] = []

    class ConsumingClient:
        name = "consume"

        async def call(self, tool_name, arguments):
            recorded.append(dict(arguments))
            if len(recorded) == 1:
                arguments.pop("nonce")
                raise UpstreamUnavailableError("down", upstream=self.name)
            return {"ok": True}

        async def health_check(self):
            return True

        async def close(self):
            return None

    async def scenario() -> dict[str, object]:
        client = ConsumingClient()
        wrapped = PolicyUpstream(
            client,
            max_attempts=2,
            idempotent_tools=frozenset({"read"}),
            retry_delay=0.0,
        )
        args = {"nonce": "abc", "query": "x"}
        result = await wrapped.call("read", args)
        assert result == {"ok": True}
        assert len(recorded) == 2
        return args

    args = asyncio.run(scenario())
    # The retry must re-issue the ORIGINAL arguments, not the mutated dict.
    assert recorded[1] == {"nonce": "abc", "query": "x"}
    # The caller's dict must not be mutated as a side effect.
    assert args == {"nonce": "abc", "query": "x"}


# ---------------------------------------------------------------------------
# GREEN: network classification that already works must not regress
# ---------------------------------------------------------------------------


def test_plain_public_addresses_classified_public():
    """GREEN: genuinely public IPv4/IPv6 addresses stay public."""
    assert _is_non_public_address("8.8.8.8") is False
    assert _is_non_public_address("1.1.1.1") is False
    assert _is_non_public_address("2001:4860:4860::8888") is False


def test_orchidv2_adjacent_block_stays_public():
    """GREEN: the ORCHIDv2 prefix is exactly ``2001:20::/28``; the adjacent
    block (``2001:30::/28``, second hextet 0x30..0x3f) is outside RFC 7343 and
    must remain classified public.  This pins the fix to /28 and prevents it
    from being widened to /27.
    """
    assert _is_non_public_address("2001:30::1") is False
    assert _is_non_public_address("2001:3f:ffff:ffff:ffff:ffff:ffff:ffff") is False


def test_private_and_special_ipv4_classified_non_public():
    """GREEN: private, loopback, link-local, CGNAT, benchmarking, and
    documentation IPv4 ranges are all classified non-public.
    """
    for address in (
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "127.0.0.1",
        "169.254.1.1",
        "100.64.0.1",
        "100.127.255.254",
        "198.18.0.1",
        "192.0.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "255.255.255.255",
    ):
        assert _is_non_public_address(address) is True, address


def test_private_and_special_ipv6_classified_non_public():
    """GREEN: loopback, ULA, link-local, docs, NAT64, 6to4, IPv4-compatible,
    and IPv4-mapped *private* addresses are all classified non-public.
    """
    for address in (
        "::1",
        "::",
        "fd00::1",
        "fe80::1",
        "2001:db8::1",
        "64:ff9b::1",
        "2002:7f00:1::1",
        "::7f00:1",
        "::a00:1",
        "::ffff:192.168.1.1",
        "::ffff:127.0.0.1",
    ):
        assert _is_non_public_address(address) is True, address


# ---------------------------------------------------------------------------
# GREEN: PolicyUpstream retry semantics that must not regress
# ---------------------------------------------------------------------------


def test_retry_counts_and_gating():
    """GREEN: retries are only attempted for explicitly idempotent tools, and
    the retry counter is updated.
    """

    class Flaky:
        name = "flaky"

        def __init__(self):
            self.calls = 0

        async def call(self, tool_name, arguments):
            self.calls += 1
            if self.calls == 1:
                raise UpstreamUnavailableError("down", upstream=self.name)
            return {"ok": True}

        async def health_check(self):
            return True

        async def close(self):
            return None

    async def scenario():
        client = Flaky()
        wrapped = PolicyUpstream(
            client,
            max_attempts=2,
            idempotent_tools=frozenset({"read"}),
            retry_delay=0.0,
        )
        result = await wrapped.call("read", {})
        assert result == {"ok": True}
        assert client.calls == 2
        assert wrapped.stats["retries"] == 1
        # Non-idempotent tool never retries.
        client2 = Flaky()
        wrapped2 = PolicyUpstream(
            client2,
            max_attempts=3,
            idempotent_tools=frozenset({"read"}),
        )
        with pytest.raises(UpstreamUnavailableError):
            await wrapped2.call("write", {})
        assert client2.calls == 1

    asyncio.run(scenario())


def test_caller_arguments_not_mutated_when_client_is_pure():
    """GREEN: when the client does not consume its arguments, the caller's dict
    is left untouched across a successful call.
    """

    class Pure:
        name = "pure"

        async def call(self, tool_name, arguments):
            return {"echo": arguments}

        async def health_check(self):
            return True

        async def close(self):
            return None

    async def scenario():
        wrapped = PolicyUpstream(Pure())
        args = {"a": 1, "b": 2}
        result = await wrapped.call("t", args)
        assert result["echo"] == {"a": 1, "b": 2}
        assert args == {"a": 1, "b": 2}

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# GREEN: resilience invariants must not regress
# ---------------------------------------------------------------------------


def test_bulkhead_validates_bounds_and_accounts_permits():
    """GREEN: AsyncBulkhead rejects bad limits and reports availability."""
    with pytest.raises(ValueError):
        resilience.AsyncBulkhead(0)
    with pytest.raises(ValueError):
        resilience.AsyncBulkhead(True)  # type: ignore[arg-type]
    bh = resilience.AsyncBulkhead(3)
    assert bh.available == 3
    assert bh.limit == 3


def test_circuit_breaker_rejects_bad_bounds():
    """GREEN: AsyncCircuitBreaker rejects non-finite / non-positive bounds."""
    with pytest.raises(ValueError):
        resilience.AsyncCircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        resilience.AsyncCircuitBreaker(recovery_timeout=float("inf"))
    with pytest.raises(ValueError):
        resilience.AsyncCircuitBreaker(recovery_timeout=-1)


# ---------------------------------------------------------------------------
# GREEN: redaction invariants must not regress
# ---------------------------------------------------------------------------


def test_redact_deterministic_and_length_preserving():
    """GREEN: redact keeps the same length and masks a fixed middle."""
    assert redaction.redact("hunter2") == "hu***r2"
    assert len(redaction.redact("hunter2")) == len("hunter2")
    assert redaction.redact("hi") == "****"
    assert redaction.redact("abcdef", show_chars=1) == "a****f"


def test_redact_dict_secret_key_recursion_and_depth_bound():
    """GREEN: redact_dict masks secret keys, recurses, and bounds depth."""
    out = redaction.redact_dict(
        {"password": "hunter2", "nested": {"token": "abc123"}, "ok": "keep"}
    )
    assert out["password"] == "hu***r2"
    assert out["nested"]["token"] == "ab**23"
    assert out["ok"] == "keep"
    deep: dict[object, object] = {}
    cur = deep
    for _ in range(300):
        cur["password"] = {}
        cur = cur["password"]
    masked = redaction.redact_dict(deep)
    # Deeply nested input must be bounded (no RecursionError); the subtree at
    # the depth bound is collapsed to the mask.
    cur = masked
    depth = 0
    while isinstance(cur, dict):
        cur = cur["password"]
        depth += 1
    assert cur == "****"
    assert depth <= redaction._MAX_REDACT_DEPTH + 1


# ---------------------------------------------------------------------------
# GREEN: env invariants must not regress
# ---------------------------------------------------------------------------


def test_env_parsing_defaults_and_bounds(monkeypatch):
    """GREEN: env handles whitespace, defaults, missing keys, and non-finite
    floats correctly.
    """
    monkeypatch.setenv("SEC35_INT", "  42  ")
    monkeypatch.setenv("SEC35_BIG", "1e400")
    monkeypatch.setenv("SEC35_SPACE", "   ")
    monkeypatch.delenv("SEC35_MISSING", raising=False)
    assert env_fn("SEC35_INT", cast=int) == 42
    assert env_fn("SEC35_MISSING", default=7) == 7
    assert env_fn("SEC35_SPACE", cast=int, default=9) == 9
    with pytest.raises(ValueError):
        env_fn("SEC35_BIG", cast=float)
    with pytest.raises(KeyError):
        env_fn("SEC35_MISSING")
    with pytest.raises(ValueError):
        env_fn("SEC35_MISSING", default=float("inf"))


def test_env_bool_validates_default():
    """GREEN: env_bool rejects a non-boolean default and parses true values."""
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("SEC35_FLAG", "YES")
    assert env_bool("SEC35_FLAG") is True
    assert env_bool("SEC35_MISSING", default=False) is False
    with pytest.raises(ValueError):
        env_bool("SEC35_MISSING", default=1)  # type: ignore[arg-type]
    monkeypatch.undo()
