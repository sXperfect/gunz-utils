"""Competing directory publishers must not replace one another."""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================

from __future__ import annotations

import os
from pathlib import Path

# =============================================================================
# THIRD-PARTY IMPORTS
# =============================================================================

import pytest

# =============================================================================
# LOCAL APPLICATION IMPORTS
# =============================================================================

from gunz_utils import fs


def test_competing_empty_directory_keeps_its_inode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "published"
    real_publish = fs._rename_directory_noreplace
    competing_inode: list[int] = []

    def interleave(
        source: Path,
        destination: Path,
    ) -> None:
        destination.mkdir()
        competing_inode.append(destination.stat().st_ino)
        real_publish(source, destination)

    monkeypatch.setattr(fs, "_rename_directory_noreplace", interleave)
    with pytest.raises(FileExistsError):
        with fs.transactional_directory(target) as staging:
            (staging / "data").write_text("candidate", encoding="utf-8")
    assert target.stat().st_ino == competing_inode[0]
    assert list(target.iterdir()) == []
    assert list(tmp_path.glob(".published.*")) == []


def test_unsupported_publication_cleans_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unsupported(
        source: Path,
        target: Path,
    ) -> None:
        raise NotImplementedError("synthetic unsupported publication")

    monkeypatch.setattr(fs, "_rename_directory_noreplace", unsupported)
    target = tmp_path / "published"
    with pytest.raises(NotImplementedError):
        with fs.transactional_directory(target) as staging:
            (staging / "data").write_bytes(b"candidate")
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlinks required")
def test_competing_dangling_symlink_is_preserved(
    tmp_path: Path,
) -> None:
    target = tmp_path / "published"
    with pytest.raises(FileExistsError):
        with fs.transactional_directory(target) as staging:
            (staging / "data").write_bytes(b"candidate")
            target.symlink_to(tmp_path / "absent", target_is_directory=True)
    assert target.is_symlink()
    assert list(tmp_path.glob(".published.*")) == []
