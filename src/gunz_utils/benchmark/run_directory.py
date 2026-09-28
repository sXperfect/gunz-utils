"""Portable self-contained performance-run directories."""

from __future__ import annotations

import json
import os
import shutil
import stat
from pathlib import Path

from ..io import atomic_write
from .artifacts import register_artifact
from .performance import PerformanceRun


def _ensure_directory(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"{label} must be a directory")


def _open_regular_source(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if path.is_symlink():
            raise ValueError(
                "performance artifact source must be a non-symlink regular file"
            ) from exc
        raise
    try:
        info = os.fstat(descriptor)
        path_info = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(info.st_mode)
            or not stat.S_ISREG(path_info.st_mode)
            or not os.path.samestat(info, path_info)
        ):
            raise ValueError(
                "performance artifact source changed during secure open"
            )
        return descriptor, info
    except BaseException:
        os.close(descriptor)
        raise


def _copy_regular_source(source: Path, artifacts_dir: Path) -> Path:
    source_fd, source_info = _open_regular_source(source)
    output_fd = -1
    target: Path | None = None
    try:
        first = artifacts_dir / source.name
        if first.exists() and not first.is_symlink():
            try:
                if os.path.samefile(source, first):
                    return first
            except OSError:
                pass

        suffix = 0
        while True:
            target = (
                first
                if suffix == 0
                else artifacts_dir / f"{source.stem}-{suffix}{source.suffix}"
            )
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            mode = stat.S_IMODE(source_info.st_mode) & 0o777
            try:
                output_fd = os.open(target, flags, mode or 0o600)
                break
            except FileExistsError:
                suffix += 1

        with os.fdopen(source_fd, "rb") as source_handle:
            source_fd = -1
            with os.fdopen(output_fd, "wb") as target_handle:
                output_fd = -1
                shutil.copyfileobj(
                    source_handle,
                    target_handle,
                    length=1 << 20,
                )
                target_handle.flush()
                os.fsync(target_handle.fileno())
        return target
    except BaseException:
        if target is not None:
            target.unlink(missing_ok=True)
        raise
    finally:
        if source_fd >= 0:
            os.close(source_fd)
        if output_fd >= 0:
            os.close(output_fd)


def save_run_directory(
    run: PerformanceRun,
    directory: str | Path,
    *,
    copy_artifacts: bool = True,
) -> PerformanceRun:
    """Write run.json and optionally copy registered artifacts safely."""
    root = Path(directory)
    _ensure_directory(root, label="run directory")
    updated = run
    if copy_artifacts:
        updated = type(run)(
            **{
                **run.__dict__,
                "artifacts": (),
            }
        )
        artifacts_dir = root / "artifacts"
        _ensure_directory(artifacts_dir, label="artifacts directory")
        for artifact in run.artifacts:
            source = Path(artifact.path)
            target = _copy_regular_source(source, artifacts_dir)
            updated = register_artifact(
                updated,
                target,
                kind=artifact.kind,
                media_type=artifact.media_type,
                description=artifact.description,
            )
    atomic_write(
        root / "run.json",
        json.dumps(updated.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return updated


__all__ = ["save_run_directory"]
