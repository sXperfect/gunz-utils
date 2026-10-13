"""Phase 45 (security lane, round 6) perpetual-audit tests.

Scope (re-audit): network, upstream_protocol, redaction, config, serialization.

Finding (RED):
  1. PolicyUpstream.call (upstream_protocol.py:398) passes ``dict(arguments)``
     — a SHALLOW copy — on every retry. The top-level dict is copied, but any
     nested mutable structure (list/dict value) is shared between attempts AND
     with the caller's original arguments. A client that mutates a nested value
     therefore (a) corrupts the caller's own nested arguments as a side effect
     and (b) makes each retry see the previous attempts' mutations, so retries
     are NOT semantically identical. This contradicts the documented guarantee
     ("Retries stay semantically identical" / "the caller's own dict is never
     mutated as a side effect") and is a NEW arg-boundary gap beyond the phase-35
     top-level-dict fix. Reproduced: with max_attempts=3 + idempotent tool, a
     client that appends to ``arguments["items"]`` sees ``['a','mutated']`` on
     attempt 2 and the caller's original list is mutated too.

Modules otherwise re-audited and found correct (GREEN pins): network (URI
authority/IPv6/IDNA/delimiter handling, SSRF protection incl. IPv4-mapped IPv6
and ORCHIDv2), redaction (nested/deep/bytes/unicode/show_chars), config (prefix
boundary, case-collision, separator edges), serialization (depth-bound, key
collision, non-finite float, deep-json bounding).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from gunz_utils.config import env_overrides
from gunz_utils.network import _is_non_public_address, build_network_uri
from gunz_utils.redaction import redact, redact_dict
from gunz_utils.serialization import json_loads, to_jsonable
from gunz_utils.upstream_protocol import PolicyUpstream, UpstreamUnavailableError

# ---------------------------------------------------------------------------
# RED: shallow-copy retry leaks nested argument mutation
# ---------------------------------------------------------------------------

class _NestedMutatingClient:
    """Client that mutates a NESTED argument structure on every call."""

    name = "svc"
    calls = 0
    seen: list[tuple[list, int]] = []

    async def call(self, tool_name: str, arguments: dict) -> dict:
        self.calls += 1
        self.seen.append((list(arguments["items"]), arguments["meta"]["count"]))
        arguments["items"].append("mutated")
        arguments["meta"]["count"] += 1
        raise UpstreamUnavailableError("retry me", upstream=self.name)

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass


def test_policy_retries_isolate_nested_argument_mutation() -> None:
    async def scenario() -> None:
        client = _NestedMutatingClient()
        policy = PolicyUpstream(
            client,
            max_attempts=3,
            retry_delay=0.0,
            idempotent_tools=frozenset({"t"}),
        )
        original = {"items": ["a"], "meta": {"count": 1}}
        with pytest.raises(UpstreamUnavailableError):
            await policy.call("t", original)

        # Every retry must see the ORIGINAL nested arguments, unchanged.
        for items, count in client.seen:
            assert items == ["a"]
            assert count == 1
        # The caller's own nested arguments must not be mutated as a side effect.
        assert original["items"] == ["a"]
        assert original["meta"]["count"] == 1

    asyncio.run(scenario())


# ---------------------------------------------------------------------------
# GREEN pins: network
# ---------------------------------------------------------------------------

def test_network_ipv4_mapped_ipv6_ssrf_protection() -> None:
    for address in [
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "::ffff:192.168.1.1",
        "::127.0.0.1",
        "::1",
    ]:
        assert _is_non_public_address(address)
    assert not _is_non_public_address("::ffff:8.8.8.8")


def test_network_uri_authority_and_delimiter_edges() -> None:
    assert build_network_uri("https", "example.com", path="a/b") == (
        "https://example.com/a/b"
    )
    uri = build_network_uri(
        "https", "host", username="u", password="p@ss:w/rd?x"
    )
    assert "@" in uri and "p%40ss%3Aw%2Frd%3Fx" in uri
    with pytest.raises(ValueError):
        build_network_uri("https", "[notipv6]", port=80)
    with pytest.raises(ValueError):
        build_network_uri("https", "ha st")
    with pytest.raises(ValueError):
        build_network_uri("https", "ho%st")


# ---------------------------------------------------------------------------
# GREEN pins: redaction
# ---------------------------------------------------------------------------

def test_redaction_nested_and_bytes_and_unicode() -> None:
    deep = {"k": {"k": {"secret": "TOPSECRET123"}}}
    assert "TOPSECRET" not in str(redact_dict(deep, show_chars=1))
    assert redact_dict({"token": ["a", "b"]}) == {"token": ["****", "****"]}
    assert redact(b"secret") == "****"
    masked = redact("héllo-wörld-值", show_chars=2)
    assert len(masked) == len("héllo-wörld-值")
    assert "*" in masked


def test_redaction_short_values_fully_masked() -> None:
    assert redact("hi", show_chars=2) == "****"
    assert redact("ab", show_chars=1) == "****"


# ---------------------------------------------------------------------------
# GREEN pins: config
# ---------------------------------------------------------------------------

def test_config_prefix_boundary_and_case_collision() -> None:
    result = env_overrides({"APP__FOO": "1", "XAP_PORT": "2"}, prefix="APP")
    assert "xap" not in result
    assert result["foo"] == "1"
    with pytest.raises(ValueError):
        env_overrides({"APP__A": "1", "app__A": "2"}, prefix="APP")


# ---------------------------------------------------------------------------
# GREEN pins: serialization
# ---------------------------------------------------------------------------

def test_serialization_depth_and_key_collision_bounded() -> None:
    cyclic: dict = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError):
        to_jsonable(cyclic)
    with pytest.raises(ValueError):
        to_jsonable({1: "a", "1": "b"})
    with pytest.raises(ValueError):
        to_jsonable({float("nan")})
    with pytest.raises(ValueError):
        json_loads("[" * 200 + "]" * 200)
    with pytest.raises(json.JSONDecodeError):
        json_loads(b"\xff\xfe")


def test_serialization_set_deterministic() -> None:
    assert to_jsonable({"b", "a", "c"}) == ["a", "b", "c"]
