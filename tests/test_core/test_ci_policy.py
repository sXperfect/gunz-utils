"""Static contract tests for the hosted CI policy."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
LEGACY_DOCS_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy_docs.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_triggers_only_main_pushes_and_main_pull_requests() -> None:
    text = _workflow_text()
    assert 'push:\n    branches: ["main"]' in text
    assert 'pull_request:\n    branches: ["main"]' in text
    assert "develop" not in text
    assert "workflow_dispatch" not in text


def test_ci_has_one_verify_job() -> None:
    text = _workflow_text()
    jobs = text.split("\njobs:\n", 1)[1]
    job_names = re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE)
    assert job_names == ["verify"]
    assert "name: verify" in jobs


def test_ci_is_read_only_and_cancels_superseded_runs() -> None:
    text = _workflow_text()
    assert "permissions:\n  contents: read" in text
    assert "cancel-in-progress: true" in text


def test_release_check_is_first_verification_command() -> None:
    text = _workflow_text()
    release = text.index("python scripts/release.py check")
    lint = text.index("python -m ruff check")
    tests = text.index("python -m pytest")
    assert release < lint < tests


def test_legacy_docs_workflow_is_removed() -> None:
    assert not LEGACY_DOCS_WORKFLOW.exists()
