"""Regression tests for security-audit fixes spanning core modules."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from gunz_utils.fs import transactional_directory
from gunz_utils.hashing import directory_manifest


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_transactional_directory_rejects_symlink_target(
    tmp_path: Path,
) -> None:
    real_target = tmp_path / "real-target"
    real_target.mkdir()
    target = tmp_path / "published"
    try:
        target.symlink_to(real_target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")

    with pytest.raises(FileExistsError):
        with transactional_directory(target) as staging:
            (staging / "value.txt").write_text(
                "value",
                encoding="utf-8",
            )


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_directory_manifest_does_not_escape_through_directory_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "inside.txt").write_text("inside", encoding="utf-8")

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = root / "external"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")

    manifest = directory_manifest(root)

    assert "inside.txt" in manifest
    assert all("secret.txt" not in path for path in manifest)
