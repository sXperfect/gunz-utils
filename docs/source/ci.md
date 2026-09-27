# CI & Local Gate Reference

This page documents the canonical CI configuration for `gunz-utils` and the
local runner that mirrors it. A passing hosted run means the same thing as a
passing local gate.

## Canonical location

- Hosted: `.github/workflows/ci.yml`
- Local: `scripts/ci.py` (a thin dispatcher that runs the identical commands)

Docs building is consolidated into the `docs` job of `ci.yml`; the legacy
`.github/workflows/deploy_docs.yml` is obsolete and disabled (see below).

## CI jobs and what they validate

| Job | Validates | Local command |
|-----|-----------|---------------|
| `test` (Python 3.11) | Full pytest collection (712) | `python scripts/ci.py test` |
| `compat` (Python 3.12) | Full pytest collection on 3.12 (compatibility guarantee) | `python scripts/ci.py test` (on 3.12) |
| `lint` (Python 3.11) | `ruff check src tests benchmarks` then `mypy src/gunz_utils` | `python scripts/ci.py lint` |
| `packaging` (Python 3.11) | Dependency-isolation matrix in fresh venvs (below) | `python scripts/ci.py packaging` |
| `docs` (Python 3.11) | Strict Sphinx build (`-W`, zero warnings) via `scripts/build_docs.sh` | `python scripts/ci.py docs` |
| `ci-result` | Aggregate gate: fails unless `test`/`compat`/`lint`/`packaging` all succeed and `docs` succeeds | — |

`ci-result` is the single stable required check for branch protection. It runs
with `if: always()` so it surfaces real failures and never hides them. The
`docs` job **always runs** on every PR, branch push, and manual run (it is not
path-filtered — job-level `paths:` is invalid Actions syntax), so a `docs`
failure or cancellation always fails the aggregate. The `ci-result` logic keeps
a defensive `skipped` acceptance branch, but with the `docs` job always running
it normally observes only `success`/`failure`.

## Supported Python versions and why

- Python **3.11** is the primary supported version (the strict floor per
  `pyproject.toml` / `AGENTS.md`).
- Python **3.12** runs the same full suite as a `compat` guarantee that the
  library stays forward-compatible.

Both are exercised with the full 712-test collection — never a subset.

## Local commands

```bash
mamba activate gunz-utils        # or: mamba run -n gunz-utils ...
python scripts/ci.py test        # full pytest (712)
python scripts/ci.py lint        # ruff + mypy
python scripts/ci.py docs        # strict sphinx build
python scripts/ci.py packaging   # dependency-isolation matrix
python scripts/ci.py all         # every gate in order, stop on first failure
```

Set `PYTHONPATH=/path/to/gunz-utils/src` so imports resolve into this worktree.

## Isolation guarantee (packaging)

Each `packaging` case runs in its own brand-new `python -m venv` under
`tmp/c05-venvs/` with no `PYTHONPATH`, so a previously installed extra can never
leak into a later case and the **installed** package is what gets exercised.
Cases: zero-dependency root import, stdlib fallback (no extras), each optional
extra in isolation (`validation`, `project`, `observability`, `secure`), real
headless `Agg` plotting, and wheel/sdist build with an outside-checkout import
(source-shadowing guard). There is no cumulative "install everything then run"
shortcut — each boundary is proven independently.

## Tool-refresh process

CI pins its tools to exact versions matching the local gate environment
(`pytest==9.0.2`, `ruff==0.14.10`, `mypy==1.19.1` in `ci.yml`). To bump a tool:

1. Update the exact pin in the relevant `ci.yml` install step.
2. Install the new version locally and run `python scripts/ci.py test` and
   `python scripts/ci.py lint` to confirm parity.
3. Commit the pin change only after both gates are green locally.

## Artifacts / cache / retention

- `actions/setup-python` `cache: pip` caches pip's wheel cache keyed by OS,
  interpreter, and the `pyproject.toml` hash (bounded, low churn).
- The `packaging` fresh venvs are **never** cached — isolation must stay fresh.
- No artifact uploads by default (builds stay lean; diagnostics live in logs and
  the `ci-result` summary). The workflow never deploys to Pages and holds
  read-only `contents: read` permissions.

## Troubleshooting

- **`test`/`compat` fail**: run `python scripts/ci.py test`; confirm
  `PYTHONPATH` points at this worktree's `src/`; check the failing test output.
- **`lint` fails**: `python scripts/ci.py lint` — fix the ruff findings or mypy
  errors; do not add `# type: ignore` or narrow the scope.
- **`docs` fails**: `python scripts/ci.py docs` — the strict `-W` build surfaces
  every Sphinx warning; fix the RST/Markdown/Sphinx issue, do not suppress `-W`.
- **`packaging` fails**: `python scripts/ci.py packaging` names the failing case;
  a failure usually means a fresh-venv install or an isolation boundary broke
  (e.g. an extra leaked, a missing-optional didn't raise, or wheel import
  shadowed the source tree).
- **`ci-result` fails**: inspect the job log — it lists each required job's
  result and emits an `::error::` for any non-success.

## Legacy `deploy_docs.yml`

`deploy_docs.yml` previously built docs on push. That build is now consolidated
into the `docs` job of `ci.yml`; the legacy workflow's job is disabled
(`if: false`) so docs are never built twice, and the file is retained only as a
placeholder pending explicit authorization to delete it.
