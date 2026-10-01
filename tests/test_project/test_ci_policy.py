"""Repository CI policy regression tests."""

from __future__ import annotations

import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _job_blocks(text: str) -> list[str]:
    """Return top-level GitHub Actions job blocks from workflow YAML text."""
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] | None = None
    in_jobs = False
    for line in lines:
        if line == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)
    return ["\n".join(block) for block in blocks]


def _self_hosted_jobs() -> list[tuple[pathlib.Path, str]]:
    jobs: list[tuple[pathlib.Path, str]] = []
    for workflow in sorted(WORKFLOWS.glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        for block in _job_blocks(text):
            if "runs-on:" in block and "self-hosted" in block:
                jobs.append((workflow, block))
    return jobs


def test_self_hosted_jobs_never_use_privileged_package_install() -> None:
    """Any present/future self-hosted job must stay non-root."""
    for workflow, job in _self_hosted_jobs():
        assert "sudo " not in job, f"{workflow}: self-hosted job uses sudo"
        assert "apt-get" not in job, f"{workflow}: self-hosted job uses apt-get"


def test_current_public_ci_remains_hosted_only() -> None:
    """gunz-utils currently intentionally has no self-hosted CI jobs."""
    assert _self_hosted_jobs() == []
