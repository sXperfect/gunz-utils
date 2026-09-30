# CI & Local Gate Reference

This page documents the canonical verification policy for `gunz-utils`.
Development is local-first: feature-branch pushes do not spend hosted runner
time. GitHub Actions verifies only changes entering or already on `main`.

## Design guides

The CI and correctness-audit rationale live under:

- `docs/design/audit/algorithm-method-audit.md`
- `docs/design/audit/proof-test-catalogue.md`
- `docs/design/audit/ci-strategy.md`
- `docs/guides/ci/design.md`
- `docs/guides/ci/lessons-learned.md`

The audit documents define how implementation claims become test evidence. The
hosted workflow retains the security properties of current `main`—immutable
action SHAs, read-only permissions, main-only triggers, cancellation, and an
early release-metadata preflight—then uses one diagnostic-dense aggregate
verifier.

## Hosted trigger policy

`.github/workflows/ci.yml` runs only for:

- a push to `main`;
- a pull request whose base branch is `main`.

It does not run for ordinary feature-branch pushes. Superseded runs for the
same pull request or ref are cancelled.

Hosted executions are bounded to preserve free-tier runner credits and storage:
- **15-Minute Timeout**: Jobs are capped at 15 minutes to prevent hanging tasks
  from draining runner minutes.
- **1-Day Ephemeral Retention**: Verification summary artifacts are stored for
  1 day (`retention-days: 1`), protecting the 500 MB account storage quota.
- **Packaging Isolation Skip**: Bypasses heavy multi-venv packaging checks on
  PRs where packaging files and extras are untouched (`--skip-packaging`).
- **Docs-Only Fast Path**: Skips the secondary Python 3.12 compatibility suite
  when a PR touches only documentation and changelogs (`--skip-compat`).

## One hosted verification job

The workflow exposes one stable required check: `CI / verify`. Checkout,
interpreter setup, a cheap release-metadata preflight, dependency installation,
verification, and summary upload all happen on one runner.

The verification itself is one aggregate command:

```bash
python scripts/audit_ci.py \
  --skip-release \
  --compat-python python3.12 \
  --summary-json tmp/ci-summary.json
```

`--skip-release` is used only in hosted CI because the workflow has already
run the release check as a cheap pre-install preflight. Local `./scripts/verify.sh`
still includes release validation in the aggregate run.

The orchestrator runs independent checks in this order:

1. release/version/changelog metadata;
2. Ruff and mypy;
3. full Python 3.11 pytest;
4. strict Sphinx documentation build;
5. packaging and dependency-isolation checks;
6. full Python 3.12 compatibility pytest.

Unlike the previous hosted sequence, a failure in one independent gate does
not hide later gate results. The orchestrator collects all statuses, writes the
summary, and only then returns a failing process status.

Prerequisite setup remains fail-fast. If checkout or dependency installation
does not succeed, downstream results would not be trustworthy.

## Why aggregate instead of fail-fast

The design optimizes diagnostic density per hosted run. A single execution can
report lint, typing, functional, documentation, packaging, and compatibility
problems together instead of requiring repeated paid runs to reveal them one at
a time.

This does not make checks less strict. Any failing gate still makes the final
job fail.

## Machine-readable result

The aggregate verifier writes a stable JSON document:

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

On GitHub Actions the same results are written to the step summary. The JSON
summary is uploaded with `if: always()` for post-failure inspection.

## Local commands

Run the same aggregate verifier used by hosted CI:

```bash
./scripts/verify.sh
```

If `python3.12` is installed, the wrapper includes the compatibility pass
automatically.

For focused diagnosis, individual gates remain available:

```bash
python scripts/ci.py release
python scripts/ci.py lint
python scripts/ci.py test
python scripts/ci.py docs
python scripts/ci.py packaging
```

The legacy `python scripts/ci.py all` command remains a simple sequential
fail-fast helper; `scripts/audit_ci.py` is the preferred pre-merge aggregate.

### Release gate

```bash
python scripts/release.py check
```

Validates package version, changelog structure, pending fragment naming, and
release metadata.

### Lint gate

```bash
python -m ruff check src tests benchmarks scripts
python -m mypy src/gunz_utils
```

Both tools are run by the gate so a Ruff failure does not suppress the mypy
result.

### Test gate

```bash
python -m pytest
```

Pytest runs the full collection without an artificial `maxfail` cap so one
run can report multiple failing tests.

To run focused or fast subset tests:

```bash
python -m pytest -m "not slow"           # Skip stress and heavy concurrency tests
python -m pytest -m "policy"             # Contract and CI governance tests only
```

For environments without `pytest` installed globally, run tests using the
pure-Python zero-dependency runner:

```bash
python scripts/run_tests.py
python scripts/run_tests.py -v -f        # Verbose, fail-fast
```

### Documentation gate

```bash
python scripts/ci.py docs
```

Builds Sphinx documentation strictly, with warnings treated as errors.

### Packaging/isolation gate

```bash
python scripts/ci.py packaging
```

Fresh virtual environments verify the zero-dependency core, optional extras,
headless plotting, and wheel/sdist installation behavior without mutating the
active environment.

## Python compatibility

Hosted CI installs both Python 3.11 and 3.12 on the same runner. Python 3.11 is
the primary verification interpreter. The aggregate orchestrator then invokes
the full test suite with `python3.12` as an independent final gate.

## Workflow supply-chain policy

External GitHub Actions are pinned to reviewed full-length commit SHAs. Do not
replace those pins with mutable major-version tags when editing the workflow.

## Tool version refresh

Hosted developer-tool pins are explicit. When changing a pin:

1. update `.github/workflows/ci.yml`;
2. install and test the same version locally;
3. run `./scripts/verify.sh`;
4. commit only after the aggregate verifier passes.

Do not add a second workflow or job merely to expose another ordinary gate.
Prefer extending the aggregate verifier unless a materially different
permission, operating-system, hardware, or security boundary requires separate
execution.

## Troubleshooting

- Aggregate status: `tmp/ci-summary.json`.
- Release: `python scripts/release.py status`.
- Ruff/mypy: `python scripts/ci.py lint`.
- Tests: `python scripts/ci.py test`.
- Docs: `python scripts/ci.py docs`.
- Packaging: `python scripts/ci.py packaging`.

For feature work, fix failures locally before opening or updating a pull
request to `main`; ordinary feature-branch pushes intentionally have no hosted
CI.
