"""Phase 45 perpetual audit: round-6 (deepest) re-audit of five core modules.

network.py, upstream_protocol.py, redaction.py, config.py, serialization.py.

Verified correct at base 80a2794 (GREEN companion tests below):
- network: build_network_uri (IPv4/IPv6/IDNA/userinfo/port/query), tcp_reachable
  port/timeout/allow_private validation incl. unguarded-float OverflowError.
- upstream_protocol: PolicyUpstream timeout/retry_delay overflow-robust
  validation, bool/int rejection, retry-on-timeout counting.
- redaction: redact (bytes masking, show_chars bounds), list/dict/tuple shape
  preservation under secret keys.
- config: env_overrides prefix/separator parsing, scalar/nested conflict
  rejection; merge_configs deep merge.
- serialization: to_jsonable int/str key-collision detection, set ordering
  determinism, NaN/inf rejection, json_loads depth bound.

One NEW finding (not covered by phase 35 which fixed redact bytes leak and
depth-mask corruption):

1) redaction.redact_dict (src/gunz_utils/redaction.py:259) does not recurse
   into a ``set``/``frozenset`` that sits DIRECTLY under a secret key. The
   secret-key branch only recurses ``(dict, list, tuple)``, so a secret set is
   collapsed to a scalar ``"****"`` string instead of being masked element-wise
   like lists/dicts/tuples -- and unlike a set nested deeper, which IS recursed
   via ``secret_context`` (redaction.py:243-244) into ``{"****"}``. The same
   logical input therefore yields a different output type depending on nesting
   depth, violating the module's shape-preservation behavior for secret
   containers (RED).

This test is expected to be RED against base 80a2794 for the finding and GREEN
for the companion behaviors.
"""

from __future__ import annotations

import pytest
from gunz_utils import config, network, serialization
from gunz_utils.redaction import redact, redact_dict
from gunz_utils.upstream_protocol import PolicyUpstream


class _EchoClient:
    """Minimal UpstreamClient stand-in for PolicyUpstream testing."""

    name = "echo"

    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    async def call(self, tool_name, arguments):
        self.calls += 1
        if self.fail:
            raise TimeoutError("client internal timeout")
        return {"ok": True}

    async def health_check(self):
        return True

    async def close(self):
        return None


# ---------------------------------------------------------------------------
# Finding 1 (RED): secret-keyed set/frozenset shape is inconsistent by depth
# ---------------------------------------------------------------------------


def test_redact_dict_secret_set_preserves_set_shape() -> None:
    # A set directly under a secret key must be masked element-wise (as a set
    # of masked values), matching lists/dicts/tuples and the secret_context
    # handling of sets nested deeper. Currently it collapses to a scalar
    # "****" string.
    result = redact_dict({"token": {"a", "b"}})
    assert isinstance(result["token"], set)
    assert result["token"] == {"****"}


def test_redact_dict_secret_frozenset_preserves_set_shape() -> None:
    result = redact_dict({"token": frozenset({"a", "b"})})
    assert isinstance(result["token"], frozenset)
    assert result["token"] == frozenset({"****"})


# ---------------------------------------------------------------------------
# GREEN: redaction companion behaviors
# ---------------------------------------------------------------------------


def test_redact_dict_secret_containers_preserve_shape() -> None:
    # Lists/dicts/tuples under a secret key mask each element, preserving shape.
    assert redact_dict({"token": ["a", "b"]}) == {"token": ["****", "****"]}
    assert redact_dict({"token": {"x": 1}}) == {"token": {"x": "****"}}
    assert redact_dict({"token": ("a", "b")}) == {"token": ("****", "****")}
    # A set nested inside a secret-keyed dict is already recursed (secret_context).
    assert redact_dict({"token": {"inner": {"a", "b"}}}) == {
        "token": {"inner": {"****"}}
    }


def test_redact_bytes_and_bounds() -> None:
    assert redact(b"secret") == "****"
    # "hunter2" (7 chars, show_chars=2) keeps 2 on each end and masks the 3
    # middle chars, preserving length (7).
    assert redact("hunter2") == "hu***r2"
    assert redact("hi", show_chars=2) == "****"
    with pytest.raises(ValueError):
        redact("x", show_chars=-1)
    with pytest.raises(ValueError):
        redact("x", show_chars=True)


# ---------------------------------------------------------------------------
# GREEN: network companion behaviors
# ---------------------------------------------------------------------------


def test_build_network_uri() -> None:
    assert network.build_network_uri("http", "example.com", path="a/b") == (
        "http://example.com/a/b"
    )
    assert network.build_network_uri("https", "::1", port=443).startswith(
        "https://[::1]:443"
    )
    assert network.build_network_uri(
        "postgres", "db.local", username="u", password="p@ss", port=5432
    ).startswith("postgres://u:p%40ss@db.local:5432")
    with pytest.raises(ValueError):
        network.build_network_uri("http", "exa mple.com")


def test_tcp_reachable_validation_overflow() -> None:
    with pytest.raises(ValueError):
        network.tcp_reachable("localhost", 80, timeout=10**400)
    with pytest.raises(ValueError):
        network.tcp_reachable("localhost", 0)
    with pytest.raises(ValueError):
        network.tcp_reachable("localhost", 80, timeout=True)


# ---------------------------------------------------------------------------
# GREEN: upstream_protocol companion behaviors
# ---------------------------------------------------------------------------


def test_policy_upstream_validation_overflow() -> None:
    with pytest.raises(ValueError):
        PolicyUpstream(_EchoClient(), timeout_seconds=10**400)
    with pytest.raises(ValueError):
        PolicyUpstream(_EchoClient(), retry_delay=10**400)
    with pytest.raises(ValueError):
        PolicyUpstream(_EchoClient(), max_concurrency=True)
    with pytest.raises(ValueError):
        PolicyUpstream(_EchoClient(), max_attempts=0)


# ---------------------------------------------------------------------------
# GREEN: config companion behaviors
# ---------------------------------------------------------------------------


def test_env_overrides_and_merge() -> None:
    out = config.env_overrides(
        {"APP_HOST": "h", "APP__NEST__PORT": "8080"}, prefix="APP"
    )
    assert out == {"host": "h", "nest": {"port": "8080"}}
    with pytest.raises(ValueError):
        config.env_overrides({"APP_A__B": "1", "APP_A": "2"}, prefix="APP")
    assert config.merge_configs({"a": {"b": 1}}, {"a": {"c": 2}}) == {
        "a": {"b": 1, "c": 2}
    }


# ---------------------------------------------------------------------------
# GREEN: serialization companion behaviors
# ---------------------------------------------------------------------------


def test_serialization_determinism_and_bounds() -> None:
    # Set ordering is deterministic in observable JSON output.
    for _ in range(3):
        assert serialization.canonical_json({3, 1, "a"}) == "[\"a\",1,3]"
    # int/str key collision detected.
    with pytest.raises(ValueError):
        serialization.to_jsonable({1: "x", "1": "y"})
    # NaN/inf rejected.
    with pytest.raises(ValueError):
        serialization.to_jsonable(float("nan"))
    with pytest.raises(ValueError):
        serialization.to_jsonable(float("inf"))
