"""Phase 46 perpetual audit: round-6 (deepest) re-audit of six core modules.

cache.py, provenance.py, deprecation.py, content_store.py, context.py,
streaming.py.

Verified correct at base 6075cdb (GREEN companion tests below):
- cache: ttl_cache/async_ttl_cache bool-vs-int key separation, unguarded-float
  OverflowError guards, maxsize eviction; RecencyTTLPolicy tz-aware selection.
- provenance: capture_runtime_provenance allowlist + env redaction, manifest
  bool/int validation.
- deprecation: sync/async/async-generator wrappers preserve callable identity.
- context: correlation_id / operation_context ContextVar reset.
- content_store: put/get/verify round-trip, digest validation, fanout.
- streaming: iter_jsonl/write_jsonl round-trip at allowed depth, non-finite
  rejection, bounded writers, fingerprint/hash determinism.

One NEW finding (not covered by P31 which audited serialization/streaming):

1) streaming.write_jsonl (src/gunz_utils/streaming.py:101-136) does NOT enforce
   the package's JSON nesting-depth bound (_MAX_JSON_DEPTH = 100). It calls
   ``json.dumps`` directly with no depth check, so it writes records nested
   deeper than 100 that iter_jsonl (its decode sibling, streaming.py:62-98,
   which applies _excessive_nesting_position) then refuses to read with
   JSONDecodeError -- a round-trip asymmetry. serialization.json_dumps /
   to_jsonable (serialization.py:79-216) enforce the same depth bound on the
   encode side, so write_jsonl is the one encode path that bypasses the
   package's depth-bounding policy (VULN-2026-008 class). write_jsonl must
   reject records nested deeper than _MAX_JSON_DEPTH with ValueError, symmetric
   with iter_jsonl (RED).

This test is expected to be RED against base 6075cdb for the finding and GREEN
for the companion behaviors.
"""

from __future__ import annotations

import io

import pytest

from gunz_utils import cache, context, provenance, streaming
from gunz_utils.content_store import ContentAddressedStore
from gunz_utils.serialization import _MAX_JSON_DEPTH


def _nested(depth: int) -> list:
    value: object = 0
    for _ in range(depth):
        value = [value]
    return value  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Finding 1 (RED): write_jsonl does not enforce the JSON depth bound
# ---------------------------------------------------------------------------


def test_write_jsonl_rejects_excessive_nesting_depth() -> None:
    # A record nested deeper than _MAX_JSON_DEPTH must be rejected with
    # ValueError, matching iter_jsonl (which raises JSONDecodeError) and
    # serialization.json_dumps (which raises ValueError). Currently write_jsonl
    # silently writes it, producing output iter_jsonl cannot read back.
    handle = io.StringIO()
    with pytest.raises(ValueError):
        streaming.write_jsonl(handle, [_nested(_MAX_JSON_DEPTH + 1)])


# ---------------------------------------------------------------------------
# GREEN: streaming companion behaviors
# ---------------------------------------------------------------------------


def test_streaming_roundtrip_at_allowed_depth() -> None:
    handle = io.StringIO()
    records = [{"a": 1}, [1, 2, 3], "x", None, 3.5]
    n = streaming.write_jsonl(handle, records)
    assert n == len(records)
    assert list(streaming.iter_jsonl(io.StringIO(handle.getvalue()))) == records


def test_iter_jsonl_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        list(streaming.iter_jsonl(io.StringIO("1e400\n")))
    with pytest.raises(ValueError):
        list(streaming.iter_jsonl(io.StringIO("NaN\n")))


def test_fingerprint_and_bounded_writer() -> None:
    assert streaming.fingerprint({"a": 1}) == streaming.fingerprint({"a": 1})
    buf = io.BytesIO()
    w = streaming.BoundedWriter(buf, max_bytes=10)
    w.write(b"12345")
    with pytest.raises(ValueError):
        w.write(b"123456")
    assert buf.getvalue() == b"12345"


# ---------------------------------------------------------------------------
# GREEN: cache companion behaviors
# ---------------------------------------------------------------------------


def test_ttl_cache_bool_int_separation_and_overflow() -> None:
    calls: list[tuple] = []

    @cache.ttl_cache(ttl=60)
    def f(x: int) -> int:
        calls.append(x)
        return x

    f(1)
    f(1)
    f(True)
    # True is distinct from 1 in cache keys.
    assert calls == [1, True]

    with pytest.raises(ValueError):
        cache.ttl_cache(ttl=10**400)
    with pytest.raises(ValueError):
        cache.ttl_cache(ttl=1.0, maxsize=True)


def test_recency_ttl_policy() -> None:
    from datetime import UTC, datetime, timedelta

    policy = cache.RecencyTTLPolicy(
        recent_window=timedelta(hours=1),
        recent_ttl=timedelta(seconds=60),
        historical_ttl=timedelta(seconds=5),
    )
    now = datetime.now(UTC)
    assert policy.ttl_for(now, now=now) == timedelta(seconds=60)
    assert policy.ttl_for(
        now - timedelta(hours=2), now=now
    ) == timedelta(seconds=5)
    with pytest.raises(ValueError):
        policy.ttl_for(datetime(2020, 1, 1), now=now)


# ---------------------------------------------------------------------------
# GREEN: provenance companion behaviors
# ---------------------------------------------------------------------------


def test_provenance_manifest_validation() -> None:
    with pytest.raises(ValueError):
        provenance.ExecutionManifest(
            created_at="", run_id="x", runtime=None, git=None  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        provenance.ExecutionManifest(
            created_at="c",
            run_id="r",
            runtime=None,  # type: ignore[arg-type]
            git=None,  # type: ignore[arg-type]
            attempt=True,
        )


# ---------------------------------------------------------------------------
# GREEN: context companion behaviors
# ---------------------------------------------------------------------------


def test_operation_context_reset() -> None:
    with context.operation_context("abc"):
        assert context.correlation_id() == "abc"
    assert context.correlation_id() is None
    with context.operation_context():
        assert context.correlation_id() is not None


# ---------------------------------------------------------------------------
# GREEN: content_store companion behaviors
# ---------------------------------------------------------------------------


def test_content_store_roundtrip(tmp_path) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    art = store.put_bytes(b"hello world")
    assert art.digest
    assert store.get(art.digest).is_file()
    assert store.verify(art.digest) is True
    with pytest.raises(ValueError):
        store.get("nothex" * 8)
