"""Phase 35 perpetual audit: round-4 (deepest) re-audit of five core modules.

upstream_protocol.py, redaction.py, resilience.py, network.py, env.py.

Verified correct at base 1f05e3f (GREEN companion tests below):
- upstream_protocol: constructor bounds (bool/neg/zero/nan/huge-int on
  timeout_seconds, retry_delay, max_concurrency, max_attempts), retry semantics
  for idempotent vs non-idempotent tools, Unavailable vs Timeout handling.
- resilience: AsyncBulkhead timeout=0 "do not wait" semantics, permit release,
  AsyncCircuitBreaker threshold/open/half-open, failure_predicate False not a
  failure, predicate raise counted as failure.
- network: build_network_uri scheme/host/port/userinfo validation, IDNA, IPv6
  bracketing, CGNAT/private address classification for external-only policy.
- env: strict env_bool parse, unset/whitespace default, non-finite float guard.

Two NEW findings in redaction.py:

1) redact() leaks bytes-like secrets verbatim (src/gunz_utils/redaction.py:120).
   ``redact()`` only masks ``str``; a ``bytes``/``bytearray``/``memoryview``
   credential is returned unchanged. This is inconsistent with ``redact_dict``
   (redaction.py:237-238 and :255-256), which masks bytes-like values under a
   secret key to ``"****"``. A caller using the single-value entry point on a
   bytes credential therefore gets the secret back verbatim -- a redaction
   leak. Expected: bytes-like secrets are masked, not returned raw (RED).

2) redact_dict() replaces deep NON-secret subtrees with the mask
   (src/gunz_utils/redaction.py:221-224). The depth guard fires at
   ``depth > _MAX_REDACT_DEPTH`` and returns the literal ``"****"`` mask for
   the whole subtree regardless of ``secret_context``. For a legitimately deep
   nested structure of non-secret data this corrupts the output (the deep
   leaves are replaced by a mask string), violating the documented contract
   that non-secret leaves are returned unchanged and the shape is preserved.
   The recursion bound must still prevent RecursionError, but non-secret data
   should be preserved (returned unchanged) rather than masked -- only secret
   context should degrade to the mask. Currently non-secret deep data is
   corrupted (RED).

This test is expected to be RED against base 1f05e3f for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import asyncio
import importlib

import pytest
from gunz_utils import network as netmod
from gunz_utils import redaction as R
from gunz_utils import resilience as RES
from gunz_utils import upstream_protocol as UP

envmod = importlib.import_module("gunz_utils.env")


def _run(coro: object) -> object:  # pragma: no cover - trivial helper
    return asyncio.run(coro)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED: redact() leaks bytes-like secrets verbatim.
# ---------------------------------------------------------------------------
def test_redact_masks_bytes_secret() -> None:
    secret = b"sk-1234567890abcdef"
    assert R.redact(secret) != secret  # must not return the raw secret


def test_redact_masks_bytearray_secret() -> None:
    secret = bytearray(b"sk-1234567890abcdef")
    assert R.redact(secret) != secret


def test_redact_masks_memoryview_secret() -> None:
    secret = memoryview(b"sk-1234567890abcdef")
    assert R.redact(secret) != bytes(secret)


# ---------------------------------------------------------------------------
# RED: redact_dict() corrupts deep non-secret data with the mask.
# ---------------------------------------------------------------------------
def _descend(d: object, levels: int) -> object:
    node = d
    for _ in range(levels):
        assert isinstance(node, dict)
        node = node["k"]
    return node


def test_redact_dict_preserves_deep_non_secret_data() -> None:
    depth = 140  # beyond _MAX_REDACT_DEPTH (128)
    root: dict[str, object] = {}
    cur = root
    for _ in range(depth):
        cur["k"] = {}
        cur = cur["k"]
    cur["leaf"] = "KEEP"
    out = R.redact_dict(root)
    node = _descend(out, depth)
    assert node == {"leaf": "KEEP"}


# ---------------------------------------------------------------------------
# GREEN: redact() str behavior (companion).
# ---------------------------------------------------------------------------
def test_redact_str_masking_and_length_preserved() -> None:
    masked = R.redact("hunter2")
    assert masked == "hu***r2"
    assert len(masked) == len("hunter2")
    assert "unter" not in masked


def test_redact_short_strings_fully_masked() -> None:
    assert R.redact("ab") == "****"
    assert R.redact("abcde") == "ab*de"
    assert R.redact("", show_chars=0) == "****"


def test_redact_show_chars_variants() -> None:
    assert R.redact("hunter2", show_chars=1) == "h*****2"
    assert R.redact("hunter2", show_chars=4) == "****"


def test_redact_non_str_scalars_unchanged() -> None:
    assert R.redact(12345) == 12345
    assert R.redact(None) is None
    assert R.redact(3.14) == 3.14


def test_redact_rejects_show_chars_bool_or_negative() -> None:
    with pytest.raises(ValueError):
        R.redact("secret", show_chars=-1)
    with pytest.raises(ValueError):
        R.redact("secret", show_chars=True)


# ---------------------------------------------------------------------------
# GREEN: redact_dict() companion behaviors.
# ---------------------------------------------------------------------------
def test_redact_dict_nested_dict_and_list() -> None:
    cfg = {
        "host": "db.local",
        "db": {"password": "hunter2", "user": "app"},
        "servers": ["a", "b"],
    }
    out = R.redact_dict(cfg)
    assert out["host"] == "db.local"
    assert out["db"]["password"] == "hunter2"[:2] + "***" + "hunter2"[-2:]
    assert out["db"]["user"] == "app"
    assert out["servers"] == ["a", "b"]


def test_redact_dict_masks_bytes_like_under_secret_key() -> None:
    assert R.redact_dict({"api_key": b"secret"})["api_key"] == "****"
    assert R.redact_dict({"api_key": bytearray(b"secret")})["api_key"] == "****"
    assert R.redact_dict({"api_key": memoryview(b"secret")})["api_key"] == "****"


def test_redact_dict_masks_numeric_secret_and_none() -> None:
    assert R.redact_dict({"token": 12345})["token"] == "****"
    assert R.redact_dict({"token": None})["token"] is None


def test_redact_dict_secret_set_and_tuple() -> None:
    out = R.redact_dict({"api_key": {"a", "b"}})
    assert out["api_key"] == "****"
    out2 = R.redact_dict({"api_key": frozenset({"a", "b"})})
    assert out2["api_key"] == "****"
    out3 = R.redact_dict({"api_key": ("a", "b")})
    assert out3["api_key"] == ("****", "****")


def test_redact_dict_scalar_and_empty() -> None:
    assert R.redact_dict("just a string") == "just a string"
    assert R.redact_dict(42) == 42
    assert R.redact_dict({}) == {}


def test_redact_dict_custom_patterns() -> None:
    out = R.redact_dict(
        {"api_key": "x", "host": "h"},
        patterns=frozenset({"api_key"}),
    )
    assert out["api_key"] == "****"
    assert out["host"] == "h"


# ---------------------------------------------------------------------------
# GREEN: upstream_protocol companion behaviors.
# ---------------------------------------------------------------------------
class _Client:
    name = "c"

    def __init__(self, exc: type[BaseException] | None = None) -> None:
        self._exc = exc
        self.calls = 0

    async def call(
        self,
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return {"ok": True}

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None


def test_policy_upstream_constructor_bounds() -> None:
    c = _Client()
    for bad in [True, -1, 0, float("nan"), 10**400]:
        with pytest.raises(ValueError):
            UP.PolicyUpstream(c, timeout_seconds=bad)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        UP.PolicyUpstream(c, retry_delay=10**400)
    with pytest.raises(ValueError):
        UP.PolicyUpstream(c, max_concurrency=0)
    with pytest.raises(ValueError):
        UP.PolicyUpstream(c, max_attempts=0)


def test_policy_upstream_non_idempotent_timeout_no_retry() -> None:
    c = _Client(TimeoutError())

    async def go() -> None:
        p = UP.PolicyUpstream(c, max_attempts=3, retry_delay=0.0)
        with pytest.raises(UP.UpstreamTimeoutError):
            await p.call("t", {})
        assert c.calls == 1
        assert p.stats["retries"] == 0

    _run(go())


def test_policy_upstream_idempotent_timeout_retries_then_timeout() -> None:
    c = _Client(TimeoutError())

    async def go() -> None:
        p = UP.PolicyUpstream(
            c,
            max_attempts=3,
            retry_delay=0.0,
            idempotent_tools=frozenset({"t"}),
        )
        with pytest.raises(UP.UpstreamTimeoutError):
            await p.call("t", {})
        assert c.calls == 3
        assert p.stats["retries"] == 2
        assert p.stats["timeouts"] == 3

    _run(go())


def test_policy_upstream_idempotent_unavailable_retries_then_raises() -> None:
    c = _Client(UP.UpstreamUnavailableError("down", upstream="c"))

    async def go() -> None:
        p = UP.PolicyUpstream(
            c,
            max_attempts=3,
            retry_delay=0.0,
            idempotent_tools=frozenset({"t"}),
        )
        with pytest.raises(UP.UpstreamUnavailableError):
            await p.call("t", {})
        assert c.calls == 3
        assert p.stats["failures"] == 1

    _run(go())


def test_policy_upstream_success_and_stats_snapshot() -> None:
    c = _Client()

    async def go() -> None:
        p = UP.PolicyUpstream(c)
        assert await p.call("t", {}) == {"ok": True}
        assert p.stats["calls"] == 1

    _run(go())


def test_upstream_error_to_dict() -> None:
    err = UP.UpstreamAuthError("nope", upstream="c", tool_name="t")
    d = err.to_dict()
    assert d["error"] == "nope"
    assert d["upstream"] == "c"
    assert d["tool_name"] == "t"
    assert d["error_type"] == "UpstreamAuthError"


# ---------------------------------------------------------------------------
# GREEN: resilience companion behaviors.
# ---------------------------------------------------------------------------
def test_bulkhead_timeout_zero_does_not_wait() -> None:
    bh = RES.AsyncBulkhead(1)

    async def go() -> None:
        assert await bh.run(lambda: _noop(), timeout=0) is None

    _run(go())


async def _noop() -> None:
    return None


def test_bulkhead_timeout_zero_without_permit_times_out() -> None:
    bh = RES.AsyncBulkhead(1)

    async def slow() -> None:
        await asyncio.sleep(0.2)

    async def go() -> None:
        t = asyncio.create_task(bh.run(slow, timeout=5))
        await asyncio.sleep(0.02)
        with pytest.raises(TimeoutError):
            await bh.run(lambda: _noop(), timeout=0)
        await t
        assert bh.available == 1

    _run(go())


def test_bulkhead_rejects_bad_timeout() -> None:
    bh = RES.AsyncBulkhead(1)
    for bad in [True, -1, float("nan"), 10**400]:
        with pytest.raises(ValueError):
            _run(bh.run(lambda: _noop(), timeout=bad))  # type: ignore[arg-type]


def test_circuit_breaker_opens_and_recovers() -> None:
    cb = RES.AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=0.05)

    async def fail() -> None:
        raise RuntimeError("boom")

    async def ok() -> None:
        return None

    async def go() -> None:
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)
        assert cb.state is RES.CircuitState.OPEN
        with pytest.raises(RES.CircuitOpenError):
            await cb.call(ok)
        await asyncio.sleep(0.06)
        assert cb.state is RES.CircuitState.HALF_OPEN

    _run(go())


def test_circuit_breaker_failure_predicate_false_not_a_failure() -> None:
    cb = RES.AsyncCircuitBreaker(
        failure_threshold=1,
        failure_predicate=lambda exc: False,
    )

    async def fail() -> None:
        raise RuntimeError("boom")

    async def go() -> None:
        with pytest.raises(RuntimeError):
            await cb.call(fail)
        assert cb.state is RES.CircuitState.CLOSED

    _run(go())


def test_circuit_breaker_predicate_raise_counts_as_failure() -> None:
    cb = RES.AsyncCircuitBreaker(
        failure_threshold=1,
        failure_predicate=lambda exc: (_ for _ in ()).throw(RuntimeError("pred")),
    )

    async def fail() -> None:
        raise RuntimeError("boom")

    async def go() -> None:
        with pytest.raises(RuntimeError):
            await cb.call(fail)
        assert cb.state is RES.CircuitState.OPEN

    _run(go())


def test_circuit_breaker_rejects_bad_recovery_timeout() -> None:
    for bad in [True, -1, float("nan"), 10**400]:
        with pytest.raises(ValueError):
            RES.AsyncCircuitBreaker(recovery_timeout=bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: network companion behaviors.
# ---------------------------------------------------------------------------
def test_build_network_uri_basic_and_query() -> None:
    assert netmod.build_network_uri("https", "example.com") == "https://example.com"
    assert (
        netmod.build_network_uri("https", "example.com", query=[("a", "1"), ("a", "2")])
        == "https://example.com?a=1&a=2"
    )


def test_build_network_uri_ipv6_bracketing() -> None:
    assert netmod.build_network_uri("https", "2001:db8::1") == "https://[2001:db8::1]"
    assert netmod.build_network_uri("https", "[2001:db8::1]") == "https://[2001:db8::1]"


def test_build_network_uri_idna() -> None:
    assert netmod.build_network_uri("https", "Exämple.com") == "https://xn--exmple-cua.com"


def test_build_network_uri_rejects_bad_host_and_port() -> None:
    with pytest.raises(ValueError):
        netmod.build_network_uri("https", "exa mple.com")
    with pytest.raises(ValueError):
        netmod.build_network_uri("https", "exa/mple.com")
    with pytest.raises(ValueError):
        netmod.build_network_uri("http", "h", port=0)
    with pytest.raises(ValueError):
        netmod.build_network_uri("http", "h", port=70000)


def test_build_network_uri_password_requires_username() -> None:
    with pytest.raises(ValueError):
        netmod.build_network_uri("http", "h", password="x")


def test_is_non_public_address_classifies_cgnat_and_private() -> None:
    for addr in [
        "100.64.0.1",
        "100.127.255.254",
        "10.0.0.1",
        "127.0.0.1",
        "169.254.1.1",
        "::1",
        "fe80::1",
        "2001:db8::1",
    ]:
        assert netmod._is_non_public_address(addr) is True
    assert netmod._is_non_public_address("8.8.8.8") is False
    assert netmod._is_non_public_address("2001:4860:4860::8888") is False


def test_tcp_reachable_validates_timeout_bounds() -> None:
    for bad in [True, -1, 0, float("nan"), 10**400, 10**9]:
        with pytest.raises(ValueError):
            netmod.tcp_reachable("example.com", 443, timeout=bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: env companion behaviors.
# ---------------------------------------------------------------------------
def test_env_bool_strict_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X", " TRUE ")
    assert envmod.env_bool("X") is True
    monkeypatch.setenv("X", "off")
    assert envmod.env_bool("X") is False
    monkeypatch.setenv("X", "maybe")
    with pytest.raises(ValueError):
        envmod.env_bool("X")


def test_env_unset_and_whitespace_use_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X", raising=False)
    assert envmod.env("X", default="d") == "d"
    monkeypatch.setenv("X", "   ")
    assert envmod.env("X", default="d") == "d"
    with pytest.raises(KeyError):
        envmod.env("X")


def test_env_rejects_non_finite_float_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X", "1e400")
    with pytest.raises(ValueError):
        envmod.env("X", cast=float)
    monkeypatch.setenv("X", "nan")
    with pytest.raises(ValueError):
        envmod.env("X", cast=float)


def test_env_cast_int_and_bool_default_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("X", "5")
    assert envmod.env("X", cast=int) == 5
    with pytest.raises(ValueError):
        envmod.env_bool("X", default="yes")  # type: ignore[arg-type]
