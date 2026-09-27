"""Portable self-contained performance-run directories."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .artifacts import register_artifact
from .performance import PerformanceRun


def save_run_directory(
    run: PerformanceRun,
    directory: str | Path,
    *,
    copy_artifacts: bool = True,
) -> PerformanceRun:
    """Write run.json and optionally copy registered artifacts into one directory."""
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    updated = run
    if copy_artifacts:
        updated = type(run)(
            **{
                **run.__dict__,
                "artifacts": (),
            }
        )
        artifacts_dir = root / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        for artifact in run.artifacts:
            source = Path(artifact.path)
            target = artifacts_dir / source.name
            suffix = 1
            while target.exists() and target.resolve() != source.resolve():
                target = artifacts_dir / f"{source.stem}-{suffix}{source.suffix}"
                suffix += 1
            if target.resolve() != source.resolve():
                shutil.copy2(source, target)
            updated = register_artifact(
                updated,
                target,
                kind=artifact.kind,
                media_type=artifact.media_type,
                description=artifact.description,
            )
    (root / "run.json").write_text(
        json.dumps(updated.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return updated


__all__ = ["save_run_directory"]
