"""Perpetual security audit phase 37 (round 4, deepest).

Re-audit of ``provenance``, ``security``, ``cache``, ``deprecation``, and
``ext.secure_store``.

Findings (all NEW, not fixed in phases 1-36):

1. Provenance environment redaction is bypassable for credentials that
   contain common delimiter characters, leaking part or all of a secret
   (provenance.py:51-116).

   - ``_USERINFO_PASSWORD`` (provenance.py:61) matches
     ``([^@:/]+):([^@/]*)@``.  The password group ``[^@/]*`` cannot contain
     ``/`` or ``@``, so a userinfo password containing either delimiter is
     left *completely unredacted*.  E.g.
     ``http://alice:pa/ss@db.example.com`` is returned verbatim, exposing the
     full password ``pa/ss``.

   - ``_SECRET_KEY_VALUE_TOKEN`` (provenance.py:51) matches a secret-named
     ``key=value`` token with the value class ``[^&\\s;]*``, which stops at
     ``&``, ``;``, and whitespace.  A secret value containing one of those
     characters (``&`` and ``;`` are extremely common in passwords) is only
     masked up to the delimiter, leaking the tail.  E.g.
     ``password=pa&ss`` is redacted to ``password=****&ss``, leaking ``&ss``.

   Correct behavior: a matched secret value must be masked through these
   delimiter characters so no plaintext fragment of the credential survives.

2. ``deprecation.deprecated`` does not preserve async-generator-function
   identity (deprecation.py:53-99).  The async branch only handles coroutine
   functions via ``asyncio.iscoroutinefunction``; an async *generator*
   function (``async def ...: yield``) is *not* a coroutine function, so it
   falls through to the synchronous wrapper (deprecation.py:86).  The
   resulting wrapper still iterates (it returns the async generator object),
   but ``inspect.isasyncgenfunction(wrapped)`` flips from ``True`` to
   ``False``, so consumers that dispatch on async-generator-function-ness
   mis-handle the deprecated function.  The comment at deprecation.py:54-57
   explicitly promises identity preservation for async callables; the async
   generator case is an uncovered gap.

The remaining GREEN coverage pins correct behavior so the fixes cannot
regress: normal userinfo and key=value secrets are fully masked; a
secret-named variable is masked wholesale; ``deprecated`` preserves coroutine
identity and the async generator still iterates and warns.
"""

import asyncio
import inspect

import pytest

from gunz_utils.deprecation import GunzDeprecationWarning, deprecated
from gunz_utils.provenance import capture_runtime_provenance

# ---------------------------------------------------------------------------
# Finding 1: provenance redaction must not leak credentials containing
# delimiter characters
# ---------------------------------------------------------------------------


def test_runtime_provenance_redacts_userinfo_password_with_slash(monkeypatch):
    monkeypatch.setenv(
        "DB_URL", "http://alice:pa/ss@db.example.com:5432/mydb"
    )
    prov = capture_runtime_provenance(environment_allowlist=["DB_URL"])
    redacted = prov.environment["DB_URL"]
    # The full password must not survive redaction.
    assert "pa/ss" not in redacted
    assert "pa" not in redacted


def test_runtime_provenance_redacts_userinfo_password_with_at(monkeypatch):
    monkeypatch.setenv(
        "DB_URL", "http://alice:pa@ss@db.example.com/mydb"
    )
    prov = capture_runtime_provenance(environment_allowlist=["DB_URL"])
    redacted = prov.environment["DB_URL"]
    # Nothing after the first redaction boundary may leak the password tail.
    assert "pa" not in redacted
    assert "ss" not in redacted


def test_runtime_provenance_redacts_key_value_secret_with_ampersand(
    monkeypatch,
):
    monkeypatch.setenv(
        "DATABASE_URL", "host=h password=pa&ss pool=5"
    )
    prov = capture_runtime_provenance(environment_allowlist=["DATABASE_URL"])
    redacted = prov.environment["DATABASE_URL"]
    # The password value must be masked through the '&' delimiter.
    assert "&ss" not in redacted


def test_runtime_provenance_redacts_key_value_secret_with_semicolon(
    monkeypatch,
):
    monkeypatch.setenv(
        "DATABASE_URL", "host=h password=pa;ss pool=5"
    )
    prov = capture_runtime_provenance(environment_allowlist=["DATABASE_URL"])
    redacted = prov.environment["DATABASE_URL"]
    assert ";ss" not in redacted


# ---------------------------------------------------------------------------
# Finding 2: deprecated must preserve async-generator-function identity
# ---------------------------------------------------------------------------


def test_deprecated_preserves_async_generator_identity():
    @deprecated("use new_agen")
    async def old_agen():
        yield 1
        yield 2

    assert inspect.isasyncgenfunction(old_agen) is True


# ---------------------------------------------------------------------------
# GREEN coverage: correct behavior must be pinned so the fixes cannot regress
# ---------------------------------------------------------------------------


def test_runtime_provenance_redacts_normal_userinfo_password(monkeypatch):
    monkeypatch.setenv("DB_URL", "http://alice:supersecret@db.example.com")
    prov = capture_runtime_provenance(environment_allowlist=["DB_URL"])
    redacted = prov.environment["DB_URL"]
    assert "supersecret" not in redacted
    assert "****" in redacted


def test_runtime_provenance_redacts_normal_key_value_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "host=h password=abc123 user=u")
    prov = capture_runtime_provenance(environment_allowlist=["DATABASE_URL"])
    redacted = prov.environment["DATABASE_URL"]
    assert "abc123" not in redacted


def test_runtime_provenance_redacts_secret_named_var_wholesale(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "abc&def;ghi jkl")
    prov = capture_runtime_provenance(environment_allowlist=["API_TOKEN"])
    assert prov.environment["API_TOKEN"] == "****"


def test_deprecated_preserves_async_coroutine_identity():
    @deprecated("use new_coro")
    async def old_coro(x):
        return x + 1

    assert inspect.iscoroutinefunction(old_coro) is True


def test_deprecated_async_generator_still_iterates_and_warns():
    @deprecated("use new_agen")
    async def old_agen():
        yield 1
        yield 2

    async def collect():
        return [v async for v in old_agen()]

    with pytest.warns(GunzDeprecationWarning):
        values = asyncio.run(collect())
    assert values == [1, 2]
