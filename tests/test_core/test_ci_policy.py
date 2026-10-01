"""Static contract tests for the hosted CI policy."""

from __future__ import annotations

import re
from pathlib import Path

try:
    import pytest

    pytestmark = pytest.mark.policy
except ImportError:
    pytest = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
LEGACY_DOCS_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "deploy_docs.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ci_push_scope_is_main_with_only_explicit_integration_exception() -> None:
    text = _workflow_text()
    push_match = re.search(
        r'push:\n(?:    #.*\n)*    branches: \[(.*?)\]',
        text,
    )
    assert push_match is not None
    branches = set(re.findall(r'"([^"]+)"', push_match.group(1)))
    assert "main" in branches
    extras = branches - {"main"}
    integration_branch = "merge/algorithm-audit-main"
    assert extras <= {integration_branch}
    if integration_branch in extras:
        assert "TEMPORARY: remove merge/algorithm-audit-main" in text

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
    assert "timeout-minutes: 15" in text
    assert "retention-days: 1" in text


def test_ci_release_preflight_precedes_install_then_uses_aggregate_verifier() -> None:
    text = _workflow_text()
    fetch_tags = text.index("git fetch --tags --depth=1")
    release = text.index("python scripts/release.py check")
    early_lint = text.index("python -m ruff check src tests benchmarks scripts")
    primary_install = text.index("python -m pip install pytest==9.0.3")
    compatibility_install = text.index(
        'steps.py312.outputs.python-path }}" -m pip install pytest==9.0.3'
    )
    aggregate = text.index("python scripts/audit_ci.py")
    upload = text.index("actions/upload-artifact@")

    assert (
        fetch_tags
        < release
        < early_lint
        < primary_install
        < compatibility_install
        < aggregate
        < upload
    )
    assert "--skip-release" in text
    assert "--compat-python" in text
    assert "--skip-compat" in text
    assert "--summary-json tmp/ci-summary.json" in text
    assert "if: ${{ always() }}" in text
    assert 'base_sha="${{ github.event.pull_request.base.sha }}"' in text
    assert 'changed_files="$(git diff --name-only "$base_sha" HEAD)"' in text
    assert "git diff --name-only \"$base_ref\"...HEAD | grep -q" not in text



def test_external_actions_are_pinned_to_full_commit_shas() -> None:
    text = _workflow_text()
    uses = re.findall(r"^\s*uses:\s*([^\s#]+)", text, re.MULTILINE)
    assert uses
    for reference in uses:
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference), reference


def test_legacy_docs_workflow_is_removed() -> None:
    assert not LEGACY_DOCS_WORKFLOW.exists()
