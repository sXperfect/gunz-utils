"""Phase 46 security-lane re-audit regression tests (round 6).

Re-audits of previously-covered modules (cache, provenance, deprecation,
content_store, context, streaming) for overlooked defects:

1. cache -- ``_cache_key`` only normalizes top-level scalar arguments with
   ``_normalize_cache_value`` (bool vs int distinction). Nested structures
   (tuples) containing a bool hash identically to the corresponding int, so
   ``f((True,))`` and ``f((1,))`` share one cache entry. That is a cache key
   collision / poisoning: distinct inputs are served the same cached result.

2. deprecation -- ``@deprecated`` placed *outside* a ``@classmethod`` wraps the
   ``classmethod`` descriptor itself, which is not callable, so the wrapped
   callable raises ``TypeError: 'classmethod' object is not callable`` instead
   of invoking the method.

3. provenance -- ``_redact_userinfo_password`` requires at least one user
   character before the ``:``, so the empty-user authority form
   ``scheme://:password@host`` (e.g. ``redis://:secret@host``) is not matched
   and the URL password leaks unredacted into runtime provenance.
"""

from __future__ import annotations

import warnings

from gunz_utils.cache import ttl_cache
from gunz_utils.deprecation import deprecated
from gunz_utils.provenance import capture_runtime_provenance


def test_ttl_cache_distinguishes_nested_bool_from_int() -> None:
    """A tuple arg containing a bool must not share a cache key with the int.

    ``_normalize_cache_value`` only tags top-level scalar args, so
    ``f((True,))`` and ``f((1,))`` hash/compare equal and are served the same
    cached result (poisoning: distinct inputs -> one cached value).
    """
    calls: list[tuple[object, ...]] = []

    @ttl_cache(ttl=60)
    def classify(args: tuple[object, ...]) -> str:
        calls.append(args)
        return "bool" if isinstance(args[0], bool) else "int"

    assert classify((1,)) == "int"
    assert calls == [(1,)]

    # (True,) is a distinct key from (1,) under the bool-is-subtype-of-int
    # contract; it must recompute and return "bool".
    assert classify((True,)) == "bool"  # RED: returns cached "int"
    assert calls == [(1,), (True,)]  # RED: second call never happens


def test_ttl_cache_distinguishes_nested_bool_in_kwargs() -> None:
    """Nested bool/int collision also applies to keyword-argument values."""

    @ttl_cache(ttl=60)
    def classify(*, flag: object) -> str:
        return "bool" if isinstance(flag[0], bool) else "int"

    assert classify(flag=(1,)) == "int"
    assert classify(flag=(True,)) == "bool"  # RED: cached "int"


def test_deprecated_classmethod_wrapped_outside_still_callable() -> None:
    """``@deprecated`` outside ``@classmethod`` must not produce a broken callable.

    The classmethod descriptor is not callable, so wrapping it directly and
    then calling ``Service.old()`` raises ``TypeError`` instead of returning
    the method result.
    """

    class Service:
        @deprecated("use new_api")
        @classmethod
        def old(cls) -> str:
            return "classmethod-value"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert Service.old() == "classmethod-value"  # RED: TypeError


def test_runtime_provenance_redacts_empty_user_url_password(
    monkeypatch: object,
) -> None:
    """An empty-user authority ``scheme://:password@host`` must be redacted.

    Redis-style URLs (``redis://:password@host``) place the password in an
    authority with no username; the userinfo redactor requires a user prefix,
    so the password currently survives into captured provenance.
    """
    monkeypatch.setenv("DATABASE_URL", "redis://:supersecret@host:6379/0")
    provenance = capture_runtime_provenance(
        environment_allowlist=["DATABASE_URL"],
    )
    redacted = provenance.environment["DATABASE_URL"]
    assert "supersecret" not in redacted  # RED: password leaks
    assert "****" in redacted
