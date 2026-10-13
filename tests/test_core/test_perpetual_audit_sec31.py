"""Perpetual security audit phase 31 (round 4, deepest).

Re-audit of ``content_store``, ``fs``, ``serialization``, ``context``, and
``typed_config``.

Finding:

1. ``ContentAddressedStore.materialize`` does not reject a destination that
   resolves inside the store's own content tree, so it can silently overwrite
   and corrupt another stored artifact's content (content_store.py:717-906).

   ``materialize(digest, destination, ..., replace=True)`` stages a temporary
   copy/hardlink of the requested artifact and then ``os.replace``s it onto
   ``destination`` without checking whether ``destination`` is itself a stored
   artifact path produced by ``path_for`` (content_store.py:873-881).  Because
   every artifact is addressed by its content digest, a caller that points
   ``destination`` at ``store.path_for(other_digest)`` (accidentally or
   maliciously) clobbers ``other_digest``'s stored bytes with the new content.
   The corruption is only detected lazily by a later ``get(other_digest,
   verify=True)`` (content_store.py:938-939), and a caller using
   ``get(other_digest, verify=False)`` silently receives the corrupted path.
   Both ``strategy="copy"`` and ``strategy="hardlink"`` exhibit the behavior.

   A content store is expected to protect the integrity of its own stored
   artifacts: materializing one artifact onto another artifact's canonical
   path must be rejected (``ValueError``) rather than silently corrupting the
   store, and the unaffected artifact's content must be preserved.

The remaining audit coverage in this file pins correct behavior of these
modules so the fix cannot silently regress them: content-store verification
detects corruption, missing artifacts raise ``KeyError``, ``materialize``
preserves content for a legitimate external destination, filesystem
containment and no-replace publication hold, serialization bounds nesting and
rejects bytes/non-serializable input, and context / typed_config semantics
remain strict.
"""

import pytest

from gunz_utils import context, fs, serialization, typed_config
from gunz_utils.content_store import ContentAddressedStore

# ---------------------------------------------------------------------------
# Finding 1: materialize clobbers another stored artifact inside the store
# ---------------------------------------------------------------------------


def test_materialize_rejects_destination_inside_store_tree(tmp_path):
    """RED: materializing one artifact onto another artifact's canonical path
    (a destination inside the store) must be rejected.  Currently
    ``materialize(A, store.path_for(B), replace=True)`` succeeds and
    overwrites B's stored bytes with A's content.
    """
    store = ContentAddressedStore(tmp_path / "cas")
    artifact_a = store.put_bytes(b"AAA")
    artifact_b = store.put_bytes(b"BBB")
    with pytest.raises(ValueError):
        store.materialize(
            artifact_a.digest,
            store.path_for(artifact_b.digest),
            strategy="copy",
            replace=True,
        )


def test_materialize_does_not_corrupt_other_artifact_copy_strategy(tmp_path):
    """RED: after a (mis)directed materialize onto B's path, B's stored bytes
    must remain intact.  Currently the destination path holds A's bytes, so
    this assertion fails.
    """
    store = ContentAddressedStore(tmp_path / "cas")
    artifact_a = store.put_bytes(b"AAA")
    artifact_b = store.put_bytes(b"BBB")
    with pytest.raises(ValueError):
        store.materialize(
            artifact_a.digest,
            store.path_for(artifact_b.digest),
            strategy="copy",
            replace=True,
        )
    assert store.path_for(artifact_b.digest).read_bytes() == b"BBB"


def test_materialize_does_not_corrupt_other_artifact_hardlink_strategy(tmp_path):
    """RED: the same corruption occurs with ``strategy="hardlink"`` -- the
    hardlink replaces B's stored path with a link to A's inode.
    """
    store = ContentAddressedStore(tmp_path / "cas")
    artifact_a = store.put_bytes(b"AAA")
    artifact_b = store.put_bytes(b"BBB")
    with pytest.raises(ValueError):
        store.materialize(
            artifact_a.digest,
            store.path_for(artifact_b.digest),
            strategy="hardlink",
            replace=True,
        )
    assert store.path_for(artifact_b.digest).read_bytes() == b"BBB"


# ---------------------------------------------------------------------------
# GREEN: content-store integrity / correctness that must not regress
# ---------------------------------------------------------------------------


def test_verified_get_detects_corruption(tmp_path):
    """GREEN: a directly corrupted artifact is detected by ``get(verify=True)``
    and ``verify()`` returns False, while ``verify=False`` is an explicit opt-out.
    """
    store = ContentAddressedStore(tmp_path / "cas")
    artifact = store.put_bytes(b"ORIGINAL")
    stored = store.path_for(artifact.digest)
    stored.write_bytes(b"TAMPERED")
    with pytest.raises(ValueError):
        store.get(artifact.digest, verify=True)
    assert store.verify(artifact.digest) is False
    assert store.get(artifact.digest, verify=False).read_bytes() == b"TAMPERED"


def test_get_missing_digest_raises_keyerror(tmp_path):
    """GREEN: requesting an absent digest raises KeyError, not a filesystem error."""
    store = ContentAddressedStore(tmp_path / "cas")
    missing = "ab" * 32
    with pytest.raises(KeyError):
        store.get(missing)


def test_materialize_rejects_existing_destination_without_replace(tmp_path):
    """GREEN: with ``replace=False`` an existing destination raises FileExistsError."""
    store = ContentAddressedStore(tmp_path / "cas")
    artifact = store.put_bytes(b"DATA")
    destination = tmp_path / "out.bin"
    destination.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        store.materialize(artifact.digest, destination, replace=False)


def test_materialize_copy_to_external_destination_preserves_content(tmp_path):
    """GREEN: materializing to a legitimate external destination preserves content."""
    store = ContentAddressedStore(tmp_path / "cas")
    artifact = store.put_bytes(b"EXTERNAL-CONTENT")
    destination = tmp_path / "out.bin"
    result = store.materialize(artifact.digest, destination, strategy="copy")
    assert result == destination
    assert destination.read_bytes() == b"EXTERNAL-CONTENT"


# ---------------------------------------------------------------------------
# GREEN: fs containment and no-replace publication
# ---------------------------------------------------------------------------


def test_contained_path_rejects_escape(tmp_path):
    """GREEN: a path escaping the root is rejected."""
    with pytest.raises(ValueError):
        fs.contained_path(tmp_path, "../outside")


def test_lexical_contained_path_rejects_dotdot(tmp_path):
    """GREEN: a relative path with a ``..`` component is rejected lexically."""
    with pytest.raises(ValueError):
        fs.lexical_contained_path(tmp_path, "a/../../etc/passwd")


def test_transactional_directory_rejects_preexisting_target(tmp_path):
    """GREEN: transactional_directory refuses to publish over an existing target."""
    target = tmp_path / "tx_dir"
    target.mkdir(parents=True, exist_ok=True)
    with pytest.raises(FileExistsError):
        with fs.transactional_directory(target):
            pass


# ---------------------------------------------------------------------------
# GREEN: serialization depth bound and type rejection
# ---------------------------------------------------------------------------


def test_json_loads_bounds_deep_nesting():
    """GREEN: a pathologically nested JSON document is rejected with a
    JSONDecodeError (a ValueError) rather than an uncontrolled RecursionError.
    """
    deep = "[" * 5000 + "]" * 5000
    with pytest.raises(ValueError):
        serialization.json_loads(deep)


def test_to_jsonable_rejects_bytes():
    """GREEN: bytes are rejected rather than silently stringified."""
    with pytest.raises(TypeError):
        serialization.to_jsonable(b"abc")


def test_to_jsonable_detects_mapping_key_collision():
    """GREEN: mapping keys that collide after string normalization are rejected."""
    with pytest.raises(ValueError):
        serialization.to_jsonable({1: "a", "1": "b"})


def test_canonical_json_deterministic():
    """GREEN: canonical_json is stable regardless of mapping insertion order."""
    left = serialization.canonical_json({"b": 1, "a": [2, 3]})
    right = serialization.canonical_json({"a": [2, 3], "b": 1})
    assert left == right


# ---------------------------------------------------------------------------
# GREEN: typed_config strict boolean parsing
# ---------------------------------------------------------------------------


def test_parse_bool_accepts_true_forms():
    """GREEN: canonical true forms parse to True with case/whitespace tolerance."""
    for value in ("1", "true", "TRUE", " yes ", "on"):
        assert typed_config.parse_bool(value) is True


def test_parse_bool_accepts_false_forms():
    """GREEN: canonical false forms parse to False."""
    for value in ("0", "false", "False", " no ", "off"):
        assert typed_config.parse_bool(value) is False


def test_parse_bool_rejects_unknown_and_non_string():
    """GREEN: unknown tokens and non-string input are rejected explicitly."""
    with pytest.raises(ValueError):
        typed_config.parse_bool("maybe")
    with pytest.raises(TypeError):
        typed_config.parse_bool(1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# GREEN: context correlation semantics
# ---------------------------------------------------------------------------


def test_operation_context_nesting_restores_outer():
    """GREEN: exiting an inner context restores the outer correlation id."""
    context.ensure_correlation_id()
    outer = context.correlation_id()
    with context.operation_context("inner"):
        assert context.correlation_id() == "inner"
    assert context.correlation_id() == outer


def test_operation_context_restores_on_exception():
    """GREEN: the correlation id is restored even when the body raises."""
    context.ensure_correlation_id()
    outer = context.correlation_id()
    with pytest.raises(RuntimeError):
        with context.operation_context("boom"):
            raise RuntimeError("body failed")
    assert context.correlation_id() == outer
