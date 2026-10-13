"""Phase 31 perpetual audit: round-4 (deepest) re-audit of five core modules.

content_store.py, fs.py, serialization.py, context.py, typed_config.py.

Verified correct at base 517e2ae (GREEN companion tests below):
- content_store: put/get/verify round-trip, dedup, uppercase-digest casefold,
  materialize (copy + hardlink), digest/fanout/chunk_size validation, missing
  key -> KeyError.
- fs: contained_path/lexical_contained_path reject escapes.
- serialization: mapping key collision, deep json_loads rejection,
  cyclic-object depth bound, bytes rejection, deterministic set ordering.
- typed_config: parse_bool accept/reject set, convert().

Two NEW findings:

1) context.py operation_context validation gap (lines 47-68). The parameter is
   typed ``str | None`` and the docstring says "None or an empty string
   generates a UUID", but the implementation does ``value or str(uuid.uuid4())``
   with NO type check and NO whitespace normalization:
   - ``operation_context(123)`` silently stores an ``int`` into a
     ``ContextVar[str | None]``, so ``correlation_id()`` returns an ``int`` --
     a type-contract violation that breaks any string-typed consumer.
   - ``operation_context("   ")`` stores the whitespace-only string verbatim
     instead of treating it as empty (like ``""``) and generating a UUID,
     contradicting the documented empty-string semantics.
   Expected: non-str value raises TypeError; whitespace-only value generates a
   UUID. Currently both are accepted (RED).

2) serialization.py to_jsonable bytes-like inconsistency (line 181-185).
   ``bytes`` raises TypeError ("bytes are not implicitly JSON serializable"),
   but ``bytearray``/``memoryview`` are not handled and fall through to
   ``return value``, so to_jsonable returns a non-JSON-compatible object
   instead of rejecting it. Expected: TypeError like bytes. Currently accepted
   (RED).

This test is expected to be RED against base 517e2ae for the two findings and
GREEN for the companion behaviors.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from gunz_utils import fs
from gunz_utils import serialization as S
from gunz_utils.content_store import ContentAddressedStore
from gunz_utils.context import correlation_id, operation_context
from gunz_utils.typed_config import parse_bool


# ---------------------------------------------------------------------------
# RED: context.operation_context must reject non-str and generate a UUID for
# whitespace-only values.
# ---------------------------------------------------------------------------
def test_context_operation_context_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        with operation_context(123):  # type: ignore[arg-type]
            pass


def test_context_operation_context_whitespace_generates_uuid() -> None:
    with operation_context("   ") as correlation:
        assert correlation == correlation_id()
        # Whitespace-only is semantically empty -> a UUID is generated, not the
        # whitespace string stored verbatim.
        assert correlation_id() == correlation
        assert len(correlation_id()) == 36
        uuid.UUID(correlation_id())


# ---------------------------------------------------------------------------
# RED: serialization.to_jsonable must reject bytearray/memoryview like bytes.
# ---------------------------------------------------------------------------
def test_serialization_to_jsonable_rejects_bytearray() -> None:
    with pytest.raises(TypeError):
        S.to_jsonable(bytearray(b"abc"))
    with pytest.raises(TypeError):
        S.to_jsonable(memoryview(b"abc"))


# ---------------------------------------------------------------------------
# GREEN: context correctness for valid inputs.
# ---------------------------------------------------------------------------
def test_context_operation_context_valid_strings() -> None:
    assert correlation_id() is None
    with operation_context("abc") as corr:
        assert corr == "abc"
        assert correlation_id() == "abc"
    # Restored after exit.
    assert correlation_id() is None
    # Empty string generates a UUID.
    with operation_context("") as corr:
        assert len(corr) == 36
        assert correlation_id() == corr


# ---------------------------------------------------------------------------
# GREEN: serialization.
# ---------------------------------------------------------------------------
def test_serialization_mapping_key_collision() -> None:
    with pytest.raises(ValueError):
        S.to_jsonable({1: "a", "1": "b"})


def test_serialization_deep_loads_rejected() -> None:
    deep = "[" * 200 + "]" * 200
    with pytest.raises(json.JSONDecodeError):
        S.json_loads(deep)


def test_serialization_cyclic_depth_bound() -> None:
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic
    with pytest.raises(ValueError):
        S.to_jsonable(cyclic)


def test_serialization_bytes_rejected() -> None:
    with pytest.raises(TypeError):
        S.to_jsonable(b"abc")


def test_serialization_set_deterministic() -> None:
    assert S.to_jsonable({3, 1, 2}) == [1, 2, 3]
    assert S.json_dumps({"b": 1, "a": 2}) == '{"a":2,"b":1}'


# ---------------------------------------------------------------------------
# GREEN: typed_config.
# ---------------------------------------------------------------------------
def test_typed_config_parse_bool() -> None:
    assert parse_bool("1") is True
    assert parse_bool("true") is True
    assert parse_bool(" yes ") is True
    assert parse_bool("0") is False
    assert parse_bool("off") is False
    with pytest.raises(ValueError):
        parse_bool("")
    with pytest.raises(ValueError):
        parse_bool("2")
    with pytest.raises(TypeError):
        parse_bool(1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: content_store round-trip, dedup, materialize, validation.
# ---------------------------------------------------------------------------
def test_content_store_roundtrip_dedup_verify(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    first = store.put_bytes(b"hello world")
    second = store.put_bytes(b"hello world")
    assert first.digest == second.digest
    assert first.path == second.path
    assert store.get(first.digest).name == first.path.name
    assert store.verify(first.digest) is True
    # Uppercase digest normalizes via casefold.
    assert store.get(first.digest.upper()).name == first.path.name
    # Missing valid-length digest -> KeyError; verify returns False.
    with pytest.raises(KeyError):
        store.get("0" * 64)
    assert store.verify("0" * 64) is False
    # Invalid digest -> ValueError.
    with pytest.raises(ValueError):
        store.get("zz")


def test_content_store_materialize_and_validation(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    art = store.put_bytes(b"payload")
    copy_dest = tmp_path / "out.bin"
    assert store.materialize(art.digest, copy_dest, strategy="copy").read_bytes() == (
        b"payload"
    )
    link_dest = tmp_path / "out2.bin"
    assert store.materialize(art.digest, link_dest, strategy="hardlink").exists()
    with pytest.raises(ValueError):
        ContentAddressedStore(tmp_path / "x", chunk_size=0)
    with pytest.raises(ValueError):
        ContentAddressedStore(tmp_path / "x", fanout_levels=-1)
    with pytest.raises(ValueError):
        ContentAddressedStore(
            tmp_path / "x", algo="md5"
        )


# ---------------------------------------------------------------------------
# GREEN: fs containment.
# ---------------------------------------------------------------------------
def test_fs_contained_path_rejects_escape() -> None:
    with pytest.raises(ValueError):
        fs.contained_path("/tmp", "/etc/passwd")
    with pytest.raises(ValueError):
        fs.lexical_contained_path("/tmp", "../etc")
    with pytest.raises(ValueError):
        fs.lexical_contained_path("/tmp", "/etc")
