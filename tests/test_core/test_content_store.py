"""Content-addressed local store tests."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from gunz_utils.content_store import ContentAddressedStore


def test_content_store_put_and_get_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"hello world")
    store = ContentAddressedStore(tmp_path / "store")

    artifact = store.put(source)

    assert artifact.path.is_file()
    assert artifact.path.read_bytes() == b"hello world"
    assert artifact.size_bytes == len(b"hello world")
    assert store.get(artifact.digest) == artifact.path
    assert store.verify(artifact.digest)


def test_content_store_reuses_existing_verified_content(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("same", encoding="utf-8")
    store = ContentAddressedStore(tmp_path / "store")

    first = store.put(source)
    second = store.put(source)

    assert second == first


def test_content_store_detects_corruption(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("original", encoding="utf-8")
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put(source)

    artifact.path.write_text("corrupt", encoding="utf-8")

    assert not store.verify(artifact.digest)
    with pytest.raises(ValueError, match="corrupted"):
        store.get(artifact.digest)


def test_content_store_rejects_invalid_digest(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "store")

    with pytest.raises(ValueError, match="hexadecimal"):
        store.get("g" * store.digest_chars)

    with pytest.raises(ValueError, match="characters"):
        store.get("abcd")


def test_content_store_missing_digest_raises_key_error(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    missing = "0" * store.digest_chars

    with pytest.raises(KeyError):
        store.get(missing)


def test_content_store_rejects_symlinked_artifact_path(
    tmp_path: Path,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    artifact = store.put(source)

    artifact.path.unlink()
    external = tmp_path / "external.txt"
    external.write_text("payload", encoding="utf-8")
    try:
        artifact.path.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(ValueError, match="symlink"):
        store.get(artifact.digest)
    assert not store.verify(artifact.digest)


def test_content_store_rejects_symlink_source(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external.txt"
    external.write_text("payload", encoding="utf-8")
    source = tmp_path / "source-link.txt"
    try:
        source.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    store = ContentAddressedStore(tmp_path / "store")

    with pytest.raises(ValueError, match="non-symlink"):
        store.put(source)



def test_content_store_supports_configurable_digest_fanout(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"fanout")
    store = ContentAddressedStore(
        tmp_path / "store",
        fanout_levels=2,
        fanout_chars=2,
    )

    artifact = store.put(source)

    assert artifact.path.parent.name == artifact.digest[2:4]
    assert artifact.path.parent.parent.name == artifact.digest[:2]
    assert artifact.path.name == artifact.digest


def test_content_store_materialize_copy_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put(source)
    destination = tmp_path / "compat" / "asset.txt"

    result = store.materialize(
        artifact.digest,
        destination,
        strategy="copy",
    )

    assert result == destination
    assert destination.read_text(encoding="utf-8") == "payload"


def test_content_store_materialize_hardlink_when_supported(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put(source)
    destination = tmp_path / "compat.txt"

    try:
        store.materialize(
            artifact.digest,
            destination,
            strategy="hardlink",
            fallback_copy=False,
        )
    except OSError:
        pytest.skip("hard links are unavailable on this filesystem")

    assert destination.read_text(encoding="utf-8") == "payload"
    assert destination.stat().st_ino == artifact.path.stat().st_ino


def test_content_store_materialize_no_overwrite_and_replace(
    tmp_path: Path,
) -> None:
    first_source = tmp_path / "first.txt"
    first_source.write_text("first", encoding="utf-8")
    second_source = tmp_path / "second.txt"
    second_source.write_text("second", encoding="utf-8")
    store = ContentAddressedStore(tmp_path / "store")
    first = store.put(first_source)
    second = store.put(second_source)
    destination = tmp_path / "stable.txt"

    store.materialize(
        first.digest,
        destination,
        strategy="copy",
    )

    with pytest.raises(FileExistsError):
        store.materialize(
            second.digest,
            destination,
            strategy="copy",
        )

    store.materialize(
        second.digest,
        destination,
        strategy="copy",
        replace=True,
    )
    assert destination.read_text(encoding="utf-8") == "second"


def test_content_store_validates_fanout_and_materialization_strategy(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="fanout_levels"):
        ContentAddressedStore(
            tmp_path / "store-a",
            fanout_levels=-1,
        )

    with pytest.raises(ValueError, match="fanout_chars"):
        ContentAddressedStore(
            tmp_path / "store-b",
            fanout_chars=0,
        )

    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    store = ContentAddressedStore(tmp_path / "store-c")
    artifact = store.put(source)

    with pytest.raises(ValueError, match="strategy"):
        store.materialize(
            artifact.digest,
            tmp_path / "out.txt",
            strategy="invalid",
        )



def test_content_store_put_bytes_round_trip(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "store")

    artifact = store.put_bytes(b"streamed-payload")

    assert artifact.size_bytes == len(b"streamed-payload")
    assert artifact.path.read_bytes() == b"streamed-payload"
    assert store.verify(artifact.digest)


def test_content_store_put_stream_uses_current_stream_position(
    tmp_path: Path,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    source = io.BytesIO(b"prefix-payload")
    source.seek(len(b"prefix-"))

    artifact = store.put_stream(source)

    assert artifact.path.read_bytes() == b"payload"
    assert not source.closed


def test_content_store_put_bytes_accepts_memoryview(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "store")

    artifact = store.put_bytes(memoryview(b"memory"))

    assert artifact.path.read_bytes() == b"memory"


def test_content_store_put_bytes_rejects_non_bytes_like(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path / "store")

    with pytest.raises(TypeError, match="bytes-like"):
        store.put_bytes("text")


def test_content_store_publish_handles_concurrent_existing_target(
    tmp_path: Path,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    first = store.put_bytes(b"same")

    second = store.put_bytes(b"same")

    assert second == first
