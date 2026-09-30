# CI Design

This document records the hosted CI architecture for `gunz-utils` and the
constraints that should remain stable unless the maintainer explicitly changes
the policy.

## Goals

The CI design prioritizes:

1. correctness before merge;
2. minimal GitHub Actions usage;
3. one stable required status check;
4. fast failure on cheap checks;
5. parity between local and hosted verification;
6. no duplicate branch-push and pull-request validation.

## Trigger policy

Hosted CI runs only for:

```text
push -> main
pull request -> main
```

Hosted CI does not run for:

```text
feature branch pushes
develop pushes
pull requests targeting non-main branches
manual workflow dispatch
```

Feature branches use the local gate:

```bash
python scripts/ci.py all
```

This policy prevents ordinary development commits from consuming hosted runner
capacity while preserving a real integration gate before code reaches `main`.

## Single-runner architecture

The workflow exposes one job:

```text
CI / verify
```

All checks run sequentially on the same runner instead of creating a runner per
gate. This avoids repeated checkout, interpreter setup, dependency installation,
runner startup, and per-job billing granularity.

The job order is intentionally cheapest-first:

```text
shallow checkout + tag fetch
    ↓
release metadata check
    ↓
early Ruff lint preflight
    ↓
primary dependency install
    ↓
mypy type checking
    ↓
Python 3.11 full pytest
    ↓
strict Sphinx documentation
    ↓
packaging/dependency-isolation matrix
    ↓
Python 3.12 full pytest
```

A failure stops later expensive work automatically.

## Concurrency

The workflow uses one concurrency group per pull request or ref and cancels
superseded runs.

This matters when several commits are pushed to the same PR: only the newest
revision should consume runner time.

## Permissions

The hosted workflow uses read-only repository contents permission:

```yaml
permissions:
  contents: read
```

Checkout does not persist credentials. CI must not require repository write
access.

## Caching

`actions/setup-python` caches pip downloads using `pyproject.toml` as the
dependency cache key input.

Fresh virtual environments created by the packaging isolation matrix are never
cached. Their purpose is to prove dependency boundaries from clean installs;
only downloaded package artifacts may be reused through pip's cache.

## Release metadata gate

`python scripts/release.py check` is the first repository-specific check.

It verifies:

- strict Semantic Versioning syntax;
- changelog fragment validity and uniqueness;
- absence of stale module-level package-version literals;
- runtime version derivation from installed metadata;
- Sphinx release-version derivation;
- tag/version consistency warnings;
- minimum release impact implied by pending fragments.

Historical missing tags are warnings rather than errors because old repository
history is not rewritten merely to make the metadata look uniform.

## Local/hosted parity

The repository-local dispatcher is canonical:

```bash
python scripts/ci.py release
python scripts/ci.py lint
python scripts/ci.py test
python scripts/ci.py docs
python scripts/ci.py packaging
python scripts/ci.py all
```

GitHub Actions should invoke these repository primitives where practical instead
of reimplementing validation logic in YAML.

## Required check

Branch protection should require only:

```text
CI / verify
```

Do not require internal implementation steps independently. Keeping one stable
check name makes the workflow easier to refactor without continuously changing
branch-protection settings.

## Credit and resource bounds

To operate reliably under GitHub's free-tier resource limits:

1. **15-Minute Timeout Ceiling**: Caps the runner duration so unexpected hangs,
   network timeouts, or deadlocks do not deplete account runner minutes.
2. **1-Day Ephemeral Artifact Retention**: Verification summaries are retained
   for 1 day, preventing the shared 500 MB account storage quota from filling up.
3. **PR Diff Filtering**:
   - Skips the multi-venv packaging isolation matrix if packaging files are unchanged.
   - Skips the secondary Python 3.12 compatibility suite (`--skip-compat`) when
     changes are strictly documentation and changelog files.
4. **Standalone Local Testing**: Developers without global `pytest` can execute
   core unit and contract tests via `python scripts/run_tests.py`.

## Changes to this design

Before changing the trigger policy or splitting the single runner into multiple
jobs, evaluate:

- expected runner/minute cost;
- duplicated setup time;
- failure latency;
- whether parallelism materially improves developer throughput;
- whether the proposed check can instead remain local-only.

Do not re-enable feature-branch Actions merely for convenience.
