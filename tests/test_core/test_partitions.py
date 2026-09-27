"""Tests for stable disjoint partition manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gunz_utils.partitions import (
    PartitionManifest,
    assert_disjoint_partitions,
    partition_overlaps,
)


def test_partition_manifest_validates_and_fingerprints() -> None:
    manifest = PartitionManifest(
        {
            "train": ("a", "b"),
            "validation": ("c",),
        }
    )

    manifest.validate()
    assert len(manifest.fingerprint) == 64


def test_partition_fingerprint_is_independent_of_partition_mapping_order() -> None:
    left = PartitionManifest(
        {
            "train": ("a", "b"),
            "test": ("c",),
        }
    )
    right = PartitionManifest(
        {
            "test": ("c",),
            "train": ("a", "b"),
        }
    )

    assert left.fingerprint == right.fingerprint


def test_partition_fingerprint_preserves_item_order() -> None:
    left = PartitionManifest(
        {"items": ("a", "b")}
    )
    right = PartitionManifest(
        {"items": ("b", "a")}
    )

    assert left.fingerprint != right.fingerprint


def test_partition_manifest_rejects_duplicates_and_overlap() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        PartitionManifest(
            {"train": ("a", "a")}
        ).validate()

    with pytest.raises(ValueError, match="appears in partitions"):
        PartitionManifest(
            {
                "left": ("a",),
                "right": ("a",),
            }
        ).validate()


def test_partition_manifest_rejects_empty_or_invalid_identifiers() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        PartitionManifest({}).validate()

    with pytest.raises(ValueError, match="partition names"):
        PartitionManifest(
            {"": ("a",)}
        ).validate()

    with pytest.raises(ValueError, match="invalid item"):
        PartitionManifest(
            {"items": ("",)}
        ).validate()


def test_partition_manifest_write_is_stable_json(tmp_path: Path) -> None:
    manifest = PartitionManifest(
        {
            "b": ("2",),
            "a": ("1",),
        }
    )
    target = tmp_path / "nested" / "partitions.json"

    result = manifest.write(target)
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert result == target
    assert list(payload["partitions"]) == ["a", "b"]
    assert payload["fingerprint"] == manifest.fingerprint



def test_partition_manifest_defensively_copies_input_mapping() -> None:
    source = {
        "items": ["a", "b"],
    }
    manifest = PartitionManifest(source)

    source["items"].append("c")
    source["other"] = ["x"]

    assert manifest.partitions == {
        "items": ("a", "b"),
    }


def test_partition_manifest_mapping_is_immutable() -> None:
    manifest = PartitionManifest(
        {"items": ("a",)}
    )

    with pytest.raises(TypeError):
        manifest.partitions["other"] = ("b",)



def test_partition_overlaps_reports_only_nonempty_pairs() -> None:
    overlaps = partition_overlaps(
        {
            "train": ("a", "b"),
            "validation": ("b", "c"),
            "test": ("z",),
        }
    )

    assert overlaps == {
        ("train", "validation"): frozenset({"b"}),
    }


def test_assert_disjoint_partitions_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="train/validation"):
        assert_disjoint_partitions(
            {
                "train": ("a",),
                "validation": ("a",),
            }
        )

    assert_disjoint_partitions(
        {
            "train": ("a",),
            "validation": ("b",),
        }
    )



def test_partition_manifest_rejects_one_string_as_identifier_collection() -> None:
    with pytest.raises(ValueError, match="not one string"):
        PartitionManifest(
            {"items": "abc"}
        )
