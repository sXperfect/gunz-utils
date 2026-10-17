"""Adversarial publication tests for the CAS descriptor boundary."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path
from typing import Any

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

import gunz_utils.content_store as cas
from gunz_utils.content_store import ContentAddressedStore


@pytest.mark.parametrize("prefix", [" ", "-", "+", "_", "\t", "０"])
def test_digest_rejects_non_ascii_hex(
    tmp_path: Path,
    prefix: str,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    with pytest.raises(ValueError, match="hexadecimal"):
        store.path_for(prefix + "a" * (store.digest_chars - len(prefix)))
    with pytest.raises(ValueError, match="hexadecimal"):
        store.path_for("a_" + "a" * (store.digest_chars - 2))


@pytest.mark.parametrize(
    "algorithm", ["sha256", "sha512", "sha3_256", "blake2b", "blake2s"]
)
def test_supported_digest_lengths_normalize_uppercase(
    tmp_path: Path,
    algorithm: str,
) -> None:
    store = ContentAddressedStore(tmp_path / algorithm, algo=algorithm)
    artifact = store.put_bytes(b"normalization")
    assert store.get(artifact.digest.upper()) == artifact.path
    assert len(artifact.digest) == hashlib.new(algorithm).digest_size * 2


@pytest.mark.skipif(
    not cas._ANCHORED_IO, reason="descriptor-relative POSIX operations required"
)
@pytest.mark.parametrize("fallback", [False, True])
def test_fanout_swap_cannot_redirect_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fallback: bool,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    digest = hashlib.sha256(b"payload").hexdigest()
    parent = store.path_for(digest).parent
    detached = store.root / "detached"
    real_link, real_replace = os.link, os.replace

    def swap() -> None:
        parent.rename(detached)
        parent.symlink_to(outside, target_is_directory=True)

    def link(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if fallback:
            raise OSError(errno.EOPNOTSUPP, "hard links unsupported")
        swap()
        real_link(*args, **kwargs)

    def replace(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        swap()
        real_replace(*args, **kwargs)

    monkeypatch.setattr(cas.os, "link", link)
    if fallback:
        monkeypatch.setattr(cas.os, "replace", replace)
    with pytest.raises(ValueError, match="symlink|directory changed"):
        store.put_bytes(b"payload")
    assert list(outside.iterdir()) == []
    assert detached.joinpath(digest).read_bytes() == b"payload"
    assert list(store.root.glob(".incoming.*")) == []


def test_copy_staging_substitution_preserves_outside_victim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"artifact")
    victim = tmp_path / "victim"
    victim.write_bytes(b"original")
    target = tmp_path / "output"
    real_copy = cas.shutil.copyfileobj

    def copy(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        temporary = next(tmp_path.glob(".output.*.tmp"))
        temporary.unlink()
        temporary.symlink_to(victim)
        real_copy(*args, **kwargs)

    monkeypatch.setattr(cas.shutil, "copyfileobj", copy)
    with pytest.raises(ValueError, match="artifact changed"):
        store.materialize(artifact.digest, target)
    assert victim.read_bytes() == b"original"
    assert not target.exists()
    assert list(tmp_path.glob(".output.*")) == []


def test_copy_pins_verified_source_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"original artifact")
    real_copy = cas.shutil.copyfileobj

    def copy(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        artifact.path.unlink()
        artifact.path.write_bytes(b"substituted source")
        real_copy(*args, **kwargs)

    monkeypatch.setattr(cas.shutil, "copyfileobj", copy)
    output = store.materialize(artifact.digest, tmp_path / "output")
    assert output.read_bytes() == b"original artifact"
    assert not output.is_symlink()


@pytest.mark.skipif(not cas._ANCHORED_IO, reason="no-follow hard links required")
def test_hardlink_source_substitution_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"artifact")
    victim = tmp_path / "victim"
    victim.write_bytes(b"original")
    real_link = os.link

    def link(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if str(args[1]).endswith(".link"):
            artifact.path.unlink()
            artifact.path.symlink_to(victim)
        real_link(*args, **kwargs)

    monkeypatch.setattr(cas.os, "link", link)
    with pytest.raises(ValueError, match="artifact changed"):
        store.materialize(artifact.digest, tmp_path / "output", strategy="hardlink")
    assert victim.read_bytes() == b"original"
    assert list(tmp_path.glob(".output.*")) == []
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("operation", ["copy", "link", "replace"])
def test_materialize_failure_preserves_target_and_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"artifact")
    target = tmp_path / "output"
    replace = operation != "link"
    if replace:
        target.write_bytes(b"existing")

    def fail(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise OSError("injected failure")

    if operation == "copy":
        monkeypatch.setattr(cas.shutil, "copyfileobj", fail)
    else:
        monkeypatch.setattr(cas.os, operation, fail)
    with pytest.raises(OSError, match="injected failure"):
        store.materialize(artifact.digest, target, replace=replace)
    if replace:
        assert target.read_bytes() == b"existing"
    else:
        assert not target.exists()
    assert list(tmp_path.glob(".output.*")) == []
    assert artifact.path.read_bytes() == b"artifact"


def test_materialize_destination_competitor_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"artifact")
    target = tmp_path / "output"
    real_link = os.link

    def link(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        target.write_bytes(b"winner")
        real_link(*args, **kwargs)

    monkeypatch.setattr(cas.os, "link", link)
    with pytest.raises(FileExistsError):
        store.materialize(artifact.digest, target)
    assert target.read_bytes() == b"winner"
    assert list(tmp_path.glob(".output.*")) == []


def test_trusted_tree_fallback_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cas, "_ANCHORED_IO", False)
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"fallback")
    output = store.materialize(artifact.digest, tmp_path / "output")
    assert output.read_bytes() == b"fallback"
    assert store.verify(artifact.digest)


def test_fdopen_setup_failure_closes_duplicate_and_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    captured: list[int] = []
    original_dup = os.dup

    def duplicate(
        descriptor: int,
    ) -> int:
        result = original_dup(descriptor)
        captured.append(result)
        return result

    def fail(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        raise OSError("fdopen failed")

    monkeypatch.setattr(cas.os, "dup", duplicate)
    monkeypatch.setattr(cas.os, "fdopen", fail)
    with pytest.raises(OSError, match="fdopen failed"):
        store.put_bytes(b"synthetic")
    assert captured
    for descriptor in captured:
        with pytest.raises(OSError) as error:
            os.fstat(descriptor)
        assert error.value.errno == errno.EBADF
    assert list(store.root.glob(".incoming.*")) == []


def test_hardlink_name_collision_does_not_delete_competitor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"artifact")
    winner = tmp_path / ".output.predictable.link"
    winner.write_bytes(b"winner")
    monkeypatch.setattr(cas.secrets, "token_hex", lambda _: "predictable")
    output = store.materialize(
        artifact.digest, tmp_path / "output", strategy="hardlink"
    )
    assert output.read_bytes() == b"artifact"
    assert winner.read_bytes() == b"winner"


def test_copy_fallback_without_descriptor_permissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cas, "_ANCHORED_IO", False)
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"fallback")
    monkeypatch.delattr(cas.os, "fchmod")
    output = store.materialize(artifact.digest, tmp_path / "output")
    assert output.read_bytes() == b"fallback"


@pytest.mark.parametrize("replace", [False, True])
def test_final_staging_substitution_is_detected_without_outside_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replace: bool,
) -> None:
    """Portable name publication detects a swap but cannot undo an attacker entry."""
    store = ContentAddressedStore(tmp_path / "store")
    artifact = store.put_bytes(b"artifact")
    victim = tmp_path / "victim"
    victim.write_bytes(b"original")
    target = tmp_path / "output"
    real_publish = os.replace if replace else os.link

    def publish(
        *args: Any,
        **kwargs: Any,
    ) -> None:
        temporary = next(tmp_path.glob(".output.*.tmp"))
        temporary.unlink()
        temporary.symlink_to(victim)
        real_publish(*args, **kwargs)

    monkeypatch.setattr(cas.os, "replace" if replace else "link", publish)
    with pytest.raises(ValueError, match="artifact changed"):
        store.materialize(artifact.digest, target, replace=replace)
    assert victim.read_bytes() == b"original"
    assert target.is_symlink()
    assert list(tmp_path.glob(".output.*")) == []
