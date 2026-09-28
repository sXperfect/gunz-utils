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
    assert "timeout-minutes: 30" in text


def test_ci_release_preflight_precedes_install_then_uses_aggregate_verifier() -> None:
    text = _workflow_text()
    release = text.index("python scripts/release.py check")
    primary_install = text.index("python -m pip install pytest==9.0.3")
    compatibility_install = text.index(
        'steps.py312.outputs.python-path }}" -m pip install pytest==9.0.3'
    )
    aggregate = text.index("python scripts/audit_ci.py")
    upload = text.index("actions/upload-artifact@")

    assert release < primary_install < compatibility_install < aggregate < upload
    assert "--skip-release" in text
    assert "--compat-python" in text
    assert "--summary-json tmp/ci-summary.json" in text
    assert "if: ${{ always() }}" in text


def test_external_actions_are_pinned_to_full_commit_shas() -> None:
    text = _workflow_text()
    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    assert uses
    for reference in uses:
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference), reference


def test_legacy_docs_workflow_is_removed() -> None:
    assert not LEGACY_DOCS_WORKFLOW.exists()
