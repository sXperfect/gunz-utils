"""Static contract tests for the hosted CI policy."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
LEGACY_DOCS_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy_docs.yml"
AUDIT_BRANCH = "audit/algorithm-correctness"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_push_scope_is_main_with_only_explicit_temporary_audit_exception() -> None:
    text = _workflow_text()
    push_match = re.search(r'push:\n(?:    #.*\n)*    branches: \[(.*?)\]', text)
    assert push_match is not None
    branches = set(re.findall(r'"([^"]+)"', push_match.group(1)))
    assert "main" in branches
    extras = branches - {"main"}
    assert extras <= {AUDIT_BRANCH}
    if AUDIT_BRANCH in extras:
        assert "TEMPORARY: remove audit branch after" in text

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


def test_ci_uses_one_aggregate_verifier_after_prerequisite_setup() -> None:
    text = _workflow_text()
    primary_install = text.index("python -m pip install pytest")
    compatibility_install = text.index(
        'steps.py312.outputs.python-path }}" -m pip install pytest'
    )
    aggregate = text.index("python scripts/audit_ci.py")
    upload = text.index("actions/upload-artifact@v4")

    assert primary_install < compatibility_install < aggregate < upload
    assert "--compat-python" in text
    assert "--summary-json tmp/ci-summary.json" in text
    assert "if: ${{ always() }}" in text


def test_legacy_docs_workflow_is_removed() -> None:
    assert not LEGACY_DOCS_WORKFLOW.exists()
