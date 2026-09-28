"""Portable self-contained performance-run directories."""

from __future__ import annotations

import json
import shutil
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
            if source.is_symlink() or not source.is_file():
                raise ValueError(
                    "performance artifact source must be a non-symlink regular file"
                )
            target = artifacts_dir / source.name
            suffix = 1
            while (
                target.exists() or target.is_symlink()
            ) and target.resolve() != source.resolve():
                target = artifacts_dir / f"{source.stem}-{suffix}{source.suffix}"
                suffix += 1
            if target.resolve() != source.resolve():
                shutil.copy2(
                    source,
                    target,
                    follow_symlinks=False,
                )
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
