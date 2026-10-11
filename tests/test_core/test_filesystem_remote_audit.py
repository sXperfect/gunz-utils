"""Bounded fail-closed filesystem integrity regressions."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

# isort: split
# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# isort: split
# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils.hashing import directory_hash, directory_manifest


def _symlink(
    link: Path,
    target: Path,
    *,
    directory: bool = False,
) -> None:
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable on this host")


@pytest.mark.parametrize("fingerprint", [directory_manifest, directory_hash])
@pytest.mark.parametrize("restricted_root", [False, True])
def test_enumeration_permission_error_never_returns_partial_fingerprint(
    tmp_path: Path,
    fingerprint: Callable[[Path], object],
    restricted_root: bool,
) -> None:
    restricted = tmp_path if restricted_root else tmp_path / "restricted"
    restricted.mkdir(exist_ok=True)
    (restricted / "synthetic-data").write_bytes(b"synthetic-content")
    original = os.scandir

    def selective_failure(
        path: str | os.PathLike[str],
    ) -> Any:
        if Path(path) == restricted:
            raise PermissionError("synthetic enumeration denied")
        return original(path)

    with patch("os.scandir", side_effect=selective_failure):
        with pytest.raises(PermissionError, match="enumeration denied"):
            fingerprint(tmp_path)


def test_manifest_preserves_sorted_hashes_and_excludes_directory_links(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "z").write_bytes(b"z")
    (nested / "a").write_bytes(b"a")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "external").write_bytes(b"external")
    _symlink(root / "linked-directory", outside, directory=True)
    _symlink(root / "linked-file", outside / "external")
    manifest = directory_manifest(root)
    assert list(manifest) == ["nested/a", "z"]
    assert manifest == {
        "nested/a": hashlib.sha256(b"a").hexdigest(),
        "z": hashlib.sha256(b"z").hexdigest(),
    }


@pytest.mark.parametrize("replace_directory", [False, True])
def test_scan_to_open_replacement_never_hashes_external_content(
    tmp_path: Path,
    replace_directory: bool,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    child = root / ("nested" if replace_directory else "data")
    outside = tmp_path / "outside"
    if replace_directory:
        child.mkdir()
        (child / "data").write_bytes(b"inside")
        outside.mkdir()
        (outside / "data").write_bytes(b"outside")
    else:
        child.write_bytes(b"inside")
        outside.write_bytes(b"outside")
    original = os.scandir

    @contextmanager
    def scan_then_swap(
        path: str | os.PathLike[str],
    ) -> Any:
        with original(path) as entries:
            yield entries
        if Path(path) == root:
            child.rename(root / "saved")
            _symlink(child, outside, directory=replace_directory)

    with patch("os.scandir", side_effect=scan_then_swap):
        with pytest.raises(ValueError):
            directory_manifest(root)


def test_explicit_root_symlink_retains_resolved_root_semantics(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "data").write_bytes(b"inside")
    alias = tmp_path / "root-alias"
    _symlink(alias, root, directory=True)
    assert directory_manifest(alias) == directory_manifest(root)
