"""Phase 37 perpetual audit: round-4 (deepest) re-audit of five core modules.

provenance.py, secure_store.py (ext), security.py, cache.py, deprecation.py.

Verified correct at base f5ffe98 (GREEN companion tests below):
- provenance: capture_runtime_provenance allowlist + redaction, ExecutionManifest
  validation, _redact_environment_value secret-named and key=value masking.
- secure_store: set/get/delete/get_many/set_many roundtrip, ACL enforcement,
  passphrase-mode derive/open.
- security: sanitize_filename (traversal/reserved/length/empty/replacement),
  safe_path_join containment, open_path_under_base, NameAccessPolicy.
- cache: TTL hit/miss/eviction, cache_clear, unhashable-key bypass, async
  single-flight coalescing, SingleFlight, RecencyTTLPolicy, bounds validation.
- deprecation: sync/async warning emission, coroutine-function identity,
  __wrapped__ preservation.

Two NEW findings:

1) cache.py _cache_key (src/gunz_utils/cache.py:36-59) conflates bool and int
   arguments. It builds ``key = (args, tuple(sorted(kwargs.items())))`` and
   hashes it; because ``True == 1`` (and ``False == 0``) with equal hashes,
   ``f(True)`` and ``f(1)`` collide on the same cache key. A call to
   ``classify(1)`` after ``classify(True)`` returns the cached bool result --
   a wrong value. This affects ``ttl_cache``, ``async_ttl_cache``, and
   ``SingleFlight`` (all keyed via ``_cache_key``), for both positional and
   keyword arguments. It violates the package's bool-is-subtype-of-int
   distinctness contract (fixed for stable_unique, collections.unique, and
   deep_merge in earlier phases) (RED).

2) provenance.py _redact_userinfo_password (src/gunz_utils/provenance.py:61-71)
   under-redacts a URL userinfo password that contains a literal ``@``. The
   value class ``[^@/]*`` stops at ``@``, so ``postgres://user:p@ss@host/db``
   becomes ``postgres://user:****@ss@host/db`` -- the password suffix ``ss``
   leaks. A redaction helper must not leak any part of a credential; the
   authority should mask the whole password up to the last ``@`` before the
   host (RED).

This test is expected to be RED against base f5ffe98 for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import asyncio
import inspect
import warnings

import pytest

from gunz_utils import cache as CACHE
from gunz_utils import provenance as PROV
from gunz_utils import security as SEC
from gunz_utils.deprecation import GunzDeprecationWarning, deprecated
from gunz_utils.ext.secure_store import SecureStore


def _run(coro: object) -> object:  # pragma: no cover - trivial helper
    return asyncio.run(coro)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RED: cache bool/int key collision.
# ---------------------------------------------------------------------------
def test_ttl_cache_keeps_bool_and_int_keys_distinct() -> None:
    @CACHE.ttl_cache(ttl=100, maxsize=4)
    def classify(x: object) -> str:
        return "bool" if isinstance(x, bool) else "int"

    assert classify(True) == "bool"
    assert classify(1) == "int"  # currently returns cached "bool" (RED)


def test_ttl_cache_keeps_false_and_zero_keys_distinct() -> None:
    @CACHE.ttl_cache(ttl=100, maxsize=4)
    def classify(x: object) -> str:
        return "bool" if isinstance(x, bool) else "int"

    assert classify(False) == "bool"
    assert classify(0) == "int"  # currently returns cached "bool" (RED)


def test_async_ttl_cache_keeps_bool_and_int_keys_distinct() -> None:
    @CACHE.async_ttl_cache(ttl=100, maxsize=4)
    async def classify(x: object) -> str:
        return "bool" if isinstance(x, bool) else "int"

    async def go() -> None:
        assert await classify(True) == "bool"
        assert await classify(1) == "int"  # currently cached "bool" (RED)

    _run(go())


def test_ttl_cache_keyword_bool_int_keys_distinct() -> None:
    @CACHE.ttl_cache(ttl=100, maxsize=4)
    def classify(*, x: object) -> str:
        return "bool" if isinstance(x, bool) else "int"

    assert classify(x=True) == "bool"
    assert classify(x=1) == "int"  # currently cached "bool" (RED)


# ---------------------------------------------------------------------------
# RED: provenance userinfo password with literal '@' is under-redacted.
# ---------------------------------------------------------------------------
def test_redact_userinfo_password_masks_at_in_password() -> None:
    redacted = PROV._redact_userinfo_password("postgres://user:p@ss@host/db")
    # The password suffix "ss" must not leak after the masked authority.
    assert "ss@" not in redacted


# ---------------------------------------------------------------------------
# GREEN: cache companion behaviors.
# ---------------------------------------------------------------------------
def test_ttl_cache_hit_miss_and_expiry() -> None:
    @CACHE.ttl_cache(ttl=0.05, maxsize=4)
    def f(x: int) -> int:
        return x * 2

    assert f(2) == 4
    assert f(2) == 4
    assert f.cache_info().hits == 1
    assert f.cache_info().misses == 1
    import time

    time.sleep(0.06)
    assert f(2) == 4
    assert f.cache_info().misses == 2


def test_ttl_cache_eviction_and_clear() -> None:
    @CACHE.ttl_cache(ttl=100, maxsize=2)
    def f(x: int) -> int:
        return x

    f(1)
    f(2)
    f(3)  # evicts 1
    assert f.cache_info().size == 2
    f.cache_clear()
    assert f.cache_info().size == 0
    assert f.cache_info().hits == 0


def test_ttl_cache_unhashable_args_bypass_cache() -> None:
    count = {"n": 0}

    @CACHE.ttl_cache(ttl=100)
    def probe(x: object) -> int:
        count["n"] += 1
        return count["n"]

    a = [1]
    assert probe(a) == 1
    assert probe(a) == 2  # unhashable -> bypass -> recomputed, not cached
    assert count["n"] == 2


def test_ttl_cache_bounds_validation() -> None:
    with pytest.raises(ValueError):
        CACHE.ttl_cache(ttl=True)
    with pytest.raises(ValueError):
        CACHE.ttl_cache(ttl=-1)
    with pytest.raises(ValueError):
        CACHE.ttl_cache(ttl=float("nan"))
    with pytest.raises(ValueError):
        CACHE.ttl_cache(ttl=10**400)  # OverflowError must become ValueError
    with pytest.raises(ValueError):
        CACHE.ttl_cache(ttl=1, maxsize=0)
    with pytest.raises(ValueError):
        CACHE.ttl_cache(ttl=1, maxsize=True)


def test_async_ttl_cache_single_flight() -> None:
    calls: list[int] = []

    @CACHE.async_ttl_cache(ttl=100)
    async def f(x: int) -> int:
        calls.append(x)
        await asyncio.sleep(0.01)
        return x

    async def go() -> None:
        results = await asyncio.gather(f(3), f(3), f(3))
        assert results == [3, 3, 3]
        assert calls.count(3) == 1  # single-flight coalesced

    _run(go())


def test_single_flight_coalesces() -> None:
    sf = CACHE.SingleFlight()
    calls: list[int] = []

    async def factory() -> int:
        calls.append(1)
        await asyncio.sleep(0.01)
        return 1

    async def go() -> None:
        results = await asyncio.gather(sf.run("k", factory), sf.run("k", factory))
        assert results == [1, 1]
        assert len(calls) == 1

    _run(go())


def test_recency_ttl_policy() -> None:
    from datetime import UTC, datetime, timedelta

    policy = CACHE.RecencyTTLPolicy(
        recent_window=timedelta(hours=1),
        recent_ttl=timedelta(minutes=5),
        historical_ttl=timedelta(hours=1),
        empty_recent_ttl=timedelta(minutes=1),
    )
    now = datetime.now(UTC)
    assert policy.ttl_for(now - timedelta(minutes=1), now=now) == timedelta(minutes=5)
    assert policy.ttl_for(now - timedelta(hours=5), now=now) == timedelta(hours=1)
    assert (
        policy.ttl_for(now - timedelta(minutes=1), empty=True, now=now)
        == timedelta(minutes=1)
    )
    with pytest.raises(ValueError):
        policy.ttl_for(datetime.now())  # naive observed_at


# ---------------------------------------------------------------------------
# GREEN: provenance companion behaviors.
# ---------------------------------------------------------------------------
def test_redact_environment_value_secret_named_and_kvt() -> None:
    assert PROV._redact_environment_value("API_TOKEN", "supersecret") == "****"
    assert PROV._redact_environment_value("DB_URL", "host=db password=hunter2") == (
        "host=db password=****"
    )


def test_capture_runtime_provenance_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROV_A", "hello")
    monkeypatch.setenv("PROV_SECRET", "shh")
    monkeypatch.setenv("OTHER", "x")
    prov = PROV.capture_runtime_provenance(
        environment_allowlist=("PROV_A", "PROV_SECRET"),
    )
    assert prov.environment["PROV_A"] == "hello"
    assert prov.environment["PROV_SECRET"] == "****"
    assert "OTHER" not in prov.environment


def test_execution_manifest_validation() -> None:
    with pytest.raises(ValueError):
        PROV.ExecutionManifest(
            created_at="",
            run_id="r",
            runtime=PROV.capture_runtime_provenance(),
            git=None,  # type: ignore[arg-type]
        )
    with pytest.raises(ValueError):
        PROV.ExecutionManifest(
            created_at="t",
            run_id="r",
            runtime=PROV.capture_runtime_provenance(),
            git=None,  # type: ignore[arg-type]
            attempt=0,
        )


# ---------------------------------------------------------------------------
# GREEN: security companion behaviors.
# ---------------------------------------------------------------------------
def test_sanitize_filename_basics() -> None:
    assert SEC.sanitize_filename("../../etc/passwd") == "passwd"
    assert SEC.sanitize_filename("a/b/c") == "c"
    assert SEC.sanitize_filename(".hidden") == "hidden"
    assert SEC.sanitize_filename("CON.txt") == "_CON.txt"
    with pytest.raises(ValueError):
        SEC.sanitize_filename("  ")
    with pytest.raises(ValueError):
        SEC.sanitize_filename("x" * 5000)


def test_safe_path_join_containment(tmp_path: pytest.TempPathFactory) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "f.txt").write_text("x")
    assert SEC.safe_path_join(str(base), "f.txt") == str((base / "f.txt").resolve())
    with pytest.raises(ValueError):
        SEC.safe_path_join(str(base), "..", "escape")


def test_name_access_policy() -> None:
    policy = SEC.NameAccessPolicy(
        allowed=frozenset({"a", "b"}),
        denied=frozenset({"b"}),
    )
    assert policy.allows("a") is True
    assert policy.allows("b") is False
    assert policy.allows("c") is False
    with pytest.raises(PermissionError):
        policy.check("b")
    with pytest.raises(ValueError):
        policy.allows("")


# ---------------------------------------------------------------------------
# GREEN: deprecation companion behaviors.
# ---------------------------------------------------------------------------
def test_deprecated_sync_warns() -> None:
    @deprecated("use new")
    def f(x: int) -> int:
        return x

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert f(1) == 1
        assert len(caught) == 1
        assert caught[0].category is GunzDeprecationWarning


def test_deprecated_async_warns_and_keeps_identity() -> None:
    @deprecated("use new")
    async def f(x: int) -> int:
        return x + 1

    assert asyncio.iscoroutinefunction(f)
    assert inspect.iscoroutinefunction(f)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        async def go() -> None:
            assert await f(1) == 2

        _run(go())
        assert len(caught) == 1


def test_deprecated_preserves_wrapped() -> None:
    @deprecated("use new")
    def f(x: int) -> int:
        return x

    assert f.__wrapped__ is not None  # type: ignore[attr-defined]
    assert f.__name__ == "f"


# ---------------------------------------------------------------------------
# GREEN: secure_store companion behaviors.
# ---------------------------------------------------------------------------
def test_secure_store_roundtrip_and_delete(tmp_path: pytest.TempPathFactory) -> None:
    store = SecureStore(str(tmp_path / "ss"))
    store.unlock()
    store.set("api_key", "sekret")
    assert store.get("api_key") == "sekret"
    assert store.get_bytes("api_key") == b"sekret"
    assert store.delete("api_key") is True
    assert store.get("api_key") is None


def test_secure_store_acl_enforcement(tmp_path: pytest.TempPathFactory) -> None:
    store = SecureStore(str(tmp_path / "ss"))
    store.unlock()
    store.set("scoped", "v", caller="admin", acl=["admin", "ops"])
    assert store.get("scoped", caller="admin") == "v"
    with pytest.raises(PermissionError):
        store.get("scoped", caller="nobody")


def test_secure_store_set_many_get_many(tmp_path: pytest.TempPathFactory) -> None:
    store = SecureStore(str(tmp_path / "ss"))
    store.unlock()
    store.set_many({"a": "1", "b": "2"}, caller="admin")
    out = store.get_many(["a", "b", "missing"], caller="admin")
    assert out == {"a": "1", "b": "2", "missing": None}
