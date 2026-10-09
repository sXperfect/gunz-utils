"""Transactional publication regressions for benchmark run directories."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import gunz_utils.benchmark.run_directory as run_directory_module
from gunz_utils.benchmark import (
    PerformanceArtifact,
    PerformanceRun,
    SystemInfo,
    register_artifact,
)


def test_later_copy_failure_rolls_back_new_run_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    run = PerformanceRun("demo", SystemInfo.capture())
    run = register_artifact(run, first, kind="data")
    run = register_artifact(run, second, kind="data")

    real_copy = run_directory_module._copy_regular_source
    calls = 0

    def fail_second(source: Path, artifacts_dir: Path) -> tuple[Path, bool]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second-copy failure")
        return real_copy(source, artifacts_dir)

    monkeypatch.setattr(run_directory_module, "_copy_regular_source", fail_second)
    destination = tmp_path / "saved"

    with pytest.raises(OSError, match="second-copy"):
        run_directory_module.save_run_directory(run, destination)

    assert not destination.exists()


def test_rollback_preserves_preexisting_artifact_and_directory(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "saved"
    artifacts_dir = destination / "artifacts"
    artifacts_dir.mkdir(parents=True)
    kept = artifacts_dir / "kept.bin"
    kept.write_bytes(b"keep me")

    run = register_artifact(
        PerformanceRun("demo", SystemInfo.capture()),
        kept,
        kind="data",
    )
    missing = PerformanceArtifact(
        kind="data",
        path=str(tmp_path / "missing.bin"),
        checksum_sha256="0" * 64,
        size_bytes=0,
    )
    run = type(run)(
        **{
            **run.__dict__,
            "artifacts": (*run.artifacts, missing),
        }
    )

    with pytest.raises(FileNotFoundError):
        run_directory_module.save_run_directory(run, destination)

    assert kept.read_bytes() == b"keep me"
    assert artifacts_dir.is_dir()
    assert destination.is_dir()
    assert not (destination / "run.json").exists()


def test_rollback_failure_does_not_replace_publication_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"artifact")
    run = register_artifact(
        PerformanceRun("demo", SystemInfo.capture()),
        artifact,
        kind="data",
    )
    destination = tmp_path / "saved"
    original = RuntimeError("run.json publication failed")

    monkeypatch.setattr(
        run_directory_module,
        "atomic_write",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(original),
    )
    real_unlink = Path.unlink

    def deny_artifact_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path.parent.name == "artifacts" and path.name == "artifact.bin":
            raise PermissionError("injected cleanup failure")
        real_unlink(path, *args, **kwargs)

    with patch.object(Path, "unlink", deny_artifact_unlink):
        with pytest.raises(RuntimeError) as caught:
            run_directory_module.save_run_directory(run, destination)

    assert caught.value is original
    assert any("PermissionError" in note for note in caught.value.__notes__)
