"""Structured and directory fingerprint tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from gunz_utils.hashing import (
    directory_hash,
    directory_manifest,
    structured_hash,
)


def test_structured_hash_ignores_mapping_insertion_order() -> None:
    left = {
        "model": "x",
        "params": {"b": 2, "a": 1},
    }
    right = {
        "params": {"a": 1, "b": 2},
        "model": "x",
    }

    assert structured_hash(left) == structured_hash(right)


def test_structured_hash_supports_path_and_set_via_canonical_serialization() -> None:
    left = {
        "path": Path("data/train"),
        "labels": {"cat", "dog"},
    }
    right = {
        "labels": {"dog", "cat"},
        "path": Path("data/train"),
    }

    assert structured_hash(left) == structured_hash(right)


def test_directory_manifest_uses_sorted_posix_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "nested" / "a.txt").write_text("a", encoding="utf-8")

    manifest = directory_manifest(tmp_path)

    assert list(manifest) == [
        "nested/a.txt",
        "z.txt",
    ]


def test_directory_hash_changes_with_content_and_path(tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_text("first", encoding="utf-8")
    first = directory_hash(tmp_path)

    source.write_text("second", encoding="utf-8")
    second = directory_hash(tmp_path)
    assert second != first

    renamed = tmp_path / "b.txt"
    source.rename(renamed)
    third = directory_hash(tmp_path)
    assert third != second


def test_directory_manifest_rejects_non_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        directory_manifest(file_path)



def test_directory_manifest_excludes_symlinked_files(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "outside-link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")

    manifest = directory_manifest(tmp_path)

    assert "outside-link.txt" not in manifest


def test_directory_manifest_validates_configuration_when_empty(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="unsupported algo"):
        directory_manifest(
            tmp_path,
            algo="not-supported",
        )

    with pytest.raises(ValueError, match="chunk_size"):
        directory_manifest(
            tmp_path,
            chunk_size=0,
        )


def test_directory_manifest_rejects_boolean_chunk_size(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        directory_manifest(
            tmp_path,
            chunk_size=True,
        )


def test_structured_hash_rejects_normalized_mapping_key_collision() -> None:
    with pytest.raises(ValueError, match="mapping keys collide"):
        structured_hash({1: "integer", "1": "string"})
