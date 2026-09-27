"""Tests for generic execution provenance manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gunz_utils.benchmark.io import GitInfo
from gunz_utils.provenance import (
    ExecutionManifest,
    RuntimeProvenance,
    capture_execution_manifest,
    write_execution_manifest,
)


def test_capture_manifest_uses_explicit_environment_allowlist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("SAFE_VALUE", "visible")
    monkeypatch.setenv("SECRET_TOKEN", "do-not-capture")

    manifest = capture_execution_manifest(
        project_root=tmp_path,
        environment_keys=("SAFE_VALUE",),
        run_id="run-1",
    )

    assert manifest.run_id == "run-1"
    assert manifest.runtime.environment == {"SAFE_VALUE": "visible"}
    assert "SECRET_TOKEN" not in manifest.runtime.environment


def test_capture_manifest_copies_config_and_inputs(tmp_path: Path) -> None:
    config = {"nested": {"value": 1}}
    inputs = {"dataset": "abc"}

    manifest = capture_execution_manifest(
        project_root=tmp_path,
        config=config,
        inputs=inputs,
        run_id="copy-test",
    )
    config["nested"]["value"] = 2
    inputs["dataset"] = "changed"

    assert manifest.config["nested"]["value"] == 1
    assert manifest.inputs["dataset"] == "abc"


def test_capture_manifest_validates_attempt_and_run_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="attempt"):
        capture_execution_manifest(
            project_root=tmp_path,
            attempt=0,
        )

    with pytest.raises(ValueError, match="run_id"):
        capture_execution_manifest(
            project_root=tmp_path,
            run_id="   ",
        )


def test_write_execution_manifest_is_json_and_creates_parent(
    tmp_path: Path,
) -> None:
    manifest = capture_execution_manifest(
        project_root=tmp_path,
        config={"answer": 42},
        run_id="stable-run",
    )
    target = tmp_path / "nested" / "manifest.json"

    result = write_execution_manifest(
        manifest,
        target,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))

    assert result == target
    assert payload["run_id"] == "stable-run"
    assert payload["config"] == {"answer": 42}
    assert payload["schema_version"] == 1



def test_capture_manifest_normalizes_identifiers_and_rejects_bool_attempt(
    tmp_path: Path,
) -> None:
    manifest = capture_execution_manifest(
        project_root=tmp_path,
        run_id="  run-1  ",
        parent_run_id="  parent-1  ",
    )

    assert manifest.run_id == "run-1"
    assert manifest.parent_run_id == "parent-1"

    with pytest.raises(ValueError, match="positive integer"):
        capture_execution_manifest(
            project_root=tmp_path,
            attempt=True,
        )


def test_capture_manifest_rejects_empty_parent_run_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="parent_run_id"):
        capture_execution_manifest(
            project_root=tmp_path,
            parent_run_id="   ",
        )



def test_execution_manifest_is_deeply_immutable(tmp_path: Path) -> None:
    manifest = capture_execution_manifest(
        project_root=tmp_path,
        config={"nested": {"value": 1}},
        inputs={"items": ["a", "b"]},
        run_id="immutable",
    )

    with pytest.raises(TypeError):
        manifest.config["other"] = 2

    nested = manifest.config["nested"]
    with pytest.raises(TypeError):
        nested["value"] = 2

    items = manifest.inputs["items"]
    assert items == ("a", "b")


def test_runtime_environment_is_immutable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("VISIBLE", "yes")
    manifest = capture_execution_manifest(
        project_root=tmp_path,
        environment_keys=("VISIBLE",),
        run_id="runtime-env",
    )

    with pytest.raises(TypeError):
        manifest.runtime.environment["VISIBLE"] = "changed"


def test_execution_manifest_direct_constructor_validates_fields() -> None:
    runtime = RuntimeProvenance(
        captured_at="2026-09-27T00:00:00+00:00",
        python_version="3.11",
        python_implementation="CPython",
        platform="test",
        machine="x86_64",
        executable="/usr/bin/python",
    )
    git = GitInfo(
        commit=None,
        branch=None,
        dirty=None,
    )

    with pytest.raises(ValueError, match="run_id"):
        ExecutionManifest(
            created_at=runtime.captured_at,
            run_id="",
            runtime=runtime,
            git=git,
        )

    with pytest.raises(ValueError, match="attempt"):
        ExecutionManifest(
            created_at=runtime.captured_at,
            run_id="run",
            runtime=runtime,
            git=git,
            attempt=True,
        )

    with pytest.raises(ValueError, match="seed"):
        ExecutionManifest(
            created_at=runtime.captured_at,
            run_id="run",
            runtime=runtime,
            git=git,
            seed=True,
        )



def test_runtime_provenance_rejects_invalid_environment_names() -> None:
    from gunz_utils.provenance import capture_runtime_provenance

    with pytest.raises(ValueError, match="environment_allowlist"):
        capture_runtime_provenance(
            environment_allowlist=("",),
        )


def test_execution_manifest_rejects_invalid_package_names(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="package_names"):
        capture_execution_manifest(
            project_root=tmp_path,
            package_names=("",),
        )
