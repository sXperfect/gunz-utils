# Single-process CI strategy

## Goal

Use one hosted verification job while maximizing the number of independent
defects reported by a single paid runner invocation.

A traditional fail-fast pipeline is efficient when failures are rare, but it
often reports only the first problem. For an audit branch that is undesirable:
a Ruff error should not hide a mypy error, a test failure should not hide a
documentation failure, and a Python 3.11 problem should not prevent an
independent Python 3.12 compatibility result from being collected.

## Architecture

The hosted workflow retains exactly one job: `CI / verify`.

After checkout and interpreter/dependency setup, it launches one verification
orchestrator:

```bash
python scripts/audit_ci.py \
  --compat-python python3.12 \
  --summary-json tmp/ci-summary.json
```

The orchestrator invokes these independent gates in a stable order:

1. release/version/changelog validation;
2. Ruff plus mypy;
3. the complete pytest suite;
4. strict documentation build;
5. packaging and optional-dependency isolation;
6. complete Python 3.12 compatibility pytest.

The orchestrator records every gate result and continues after a non-zero gate
unless explicitly started with `--fail-fast`. It exits non-zero only after
the final summary is written.

Prerequisite failures such as checkout or dependency installation remain
fail-fast because downstream results would not be meaningful without a usable
environment.

## Why one hosted job

One job provides:

- one stable required status check;
- one checkout and shared download/cache setup;
- no duplicated runner startup/rounding cost;
- a single chronological diagnostic log;
- straightforward cancellation of superseded PR runs;
- enough independence inside the orchestrator to report multiple defects.

Separate jobs are appropriate only when isolation, permissions, operating
systems, or hardware are themselves part of the contract.

## Diagnostic density

Each gate is chosen to expose a different failure class.

| Gate | Main defects surfaced |
|---|---|
| Release | version/changelog/release metadata drift |
| Ruff | syntax, import, lint, and selected bug patterns |
| mypy | type-contract inconsistencies |
| Pytest | functional, boundary, adversarial, and regression defects |
| Docs | broken references, signatures, examples, Sphinx warnings |
| Packaging | missing files, dependency leaks, extras isolation, wheel/sdist |
| Python 3.12 | interpreter-version incompatibility |

Within a gate, tools should also avoid unnecessary first-failure behavior.
Pytest's normal collection reports all failing tests, Ruff reports all matching
violations, and the lint gate runs mypy even if Ruff fails.

## Result contract

The orchestrator writes a JSON document with a stable schema:

```json
{
  "schema_version": 1,
  "passed": false,
  "results": [
    {"name": "release", "returncode": 0},
    {"name": "lint", "returncode": 1}
  ]
}
```

On GitHub Actions it also appends a Markdown table to
`GITHUB_STEP_SUMMARY`. The JSON file is uploaded with `if: always()` so the
gate summary remains available even when verification fails.

## Trigger and cost policy

Hosted CI runs only for:

- pushes to `main`;
- pull requests targeting `main`.

Feature-branch pushes remain free of hosted CI runs. The audit branch can
therefore change the workflow safely without consuming hosted credits until a
PR is intentionally opened or the branch is merged.

## Credit-Conscious CI Architecture

To operate efficiently within GitHub's free-account credit and storage bounds,
the pipeline employs specific resource-bounding strategies:

1. **Strict 15-Minute Runaway Ceiling**:
   Hosted execution is capped at `timeout-minutes: 15` (reduced from 30m). Any
   unexpected deadlock, hanging subprocess, or slow network stall terminates
   promptly, preventing uncontrolled credit drainage.

2. **1-Day Ephemeral Artifact Retention**:
   The verification summary JSON is preserved for 1 day (`retention-days: 1`).
   This prevents cumulative consumption of the shared 500 MB account storage
   quota across high-frequency pull request reviews.

3. **PR Diff-Based Conditional Gates**:
   - *Packaging isolation skip*: If a PR touches neither packaging metadata
     (`pyproject.toml`, `src/gunz_utils/ext/`), nor runner scripts, the heavy
     venv isolation matrix is bypassed (`--skip-packaging`).
   - *Docs-only fast path*: If a PR modifies only documentation and changelog
     files (`docs/`, `changes/`, `*.md`), the secondary Python 3.12 compatibility
     suite is skipped (`--skip-compat`), cutting runner duration by ~40%.

4. **Zero-Dependency Local Testing**:
   For environments where `pytest` is not globally installed, developers can
   execute core tests using `python scripts/run_tests.py` backed by the
   standard-library `unittest` runner.

## Local parity

`./scripts/verify.sh` uses the same audit orchestrator. A developer can run an
individual legacy gate with `python scripts/ci.py <gate>` when debugging, but
the aggregate verifier is the preferred pre-merge evidence.

## Extension rule

When adding a new check, first ask whether it detects a failure class not
already covered. If yes, add it to the orchestrator or an existing gate before
creating another hosted job. The objective is maximum independent defect
coverage per runner, not maximum number of CI boxes.
