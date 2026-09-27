# CI & Local Gate Reference

This page documents the canonical verification policy for `gunz-utils`.
Development is local-first: feature-branch pushes do not spend hosted runner
time. GitHub Actions verifies only changes entering or already on `main`.

## Hosted trigger policy

`.github/workflows/ci.yml` runs only for:

- a push to `main`;
- a pull request whose base branch is `main`.

It does not run for feature-branch pushes, `develop`, or manual dispatch.
Superseded runs for the same pull request or ref are cancelled.

## One hosted runner

The workflow exposes one stable required check: `CI / verify`. Its steps run
sequentially on one runner so setup/download work is reused and short jobs do
not each pay separate runner-start/rounding overhead.

The order is deliberately fail-fast:

1. release/version/changelog metadata;
2. Ruff;
3. mypy;
4. full Python 3.11 pytest suite;
5. strict Sphinx documentation build;
6. packaging and optional-dependency isolation matrix;
7. full Python 3.12 compatibility pytest suite.

Cheap static checks therefore stop the run before the expensive isolation and
compatibility stages when possible.

## Local commands

The local dispatcher is the canonical implementation of repository gates:

```bash
python scripts/ci.py release
python scripts/ci.py lint
python scripts/ci.py test
python scripts/ci.py docs
python scripts/ci.py packaging
python scripts/ci.py all
```

`scripts/verify.sh` is a convenience wrapper around
`python scripts/ci.py all`.

### Release gate

```bash
python scripts/release.py check
```

This validates the `pyproject.toml` version, changelog structure, pending
fragment names/categories, absence of stale module-level package versions, and
the runtime/Sphinx version-source policy. Tag gaps are reported as warnings
rather than fabricated automatically.

See [Releases](releases.md) for the hosted-documentation summary. The full
maintainer process remains in `docs/development/releases.md`.

### Lint gate

```bash
python -m ruff check src tests benchmarks scripts
python -m mypy src/gunz_utils
```

Ruff includes repository tooling so `scripts/release.py` and the CI dispatcher
are validated rather than treated as unowned automation.

### Test gate

```bash
python -m pytest
```

The hosted workflow executes the full suite on Python 3.11 and repeats it on
Python 3.12 only after the earlier gates pass.

### Documentation gate

```bash
python scripts/ci.py docs
```

This calls `scripts/build_docs.sh`, which performs a strict Sphinx build with
warnings treated as errors.

### Packaging/isolation gate

```bash
python scripts/ci.py packaging
```

Each case runs in its own fresh `python -m venv` under `tmp/c05-venvs/` with
`PYTHONPATH` removed. The matrix verifies:

- zero-dependency package import;
- standard-library fallback behavior;
- `validation` extra in isolation;
- `project` extra in isolation;
- `observability` extra in isolation;
- `secure` extra in isolation;
- real headless plotting through the `plot` extra;
- wheel and sdist creation plus an outside-checkout wheel import.

The virtual environments are never cached. Pip's download/wheel cache may be
reused so isolation stays real without repeatedly downloading unchanged
artifacts.

## Hosted environment and caching

The workflow starts on Python 3.11 and uses `actions/setup-python` pip caching
keyed by `pyproject.toml`. CI dependencies are installed once for the primary
stages; pip itself is not upgraded on every run.

The packaging gate creates fresh virtual environments but can reuse pip's
download cache. After the primary gates pass, the same job switches to Python
3.12, installs the compatibility-test requirements, and runs the complete test
suite.

No build artifacts are uploaded by default. The workflow has read-only
`contents: read` permission.

## Tool version refresh

Hosted developer-tool pins are explicit. To update one:

1. update the relevant pin in `.github/workflows/ci.yml`;
2. install/test the same version locally;
3. run `python scripts/ci.py all`;
4. commit only after local verification succeeds.

Do not add a second workflow merely to test another gate. Prefer extending the
local dispatcher and the single `verify` job unless a materially different
security/permission boundary requires separation.

## Troubleshooting

- Release gate: `python scripts/release.py status` and
  `python scripts/release.py check`.
- Ruff/mypy: `python scripts/ci.py lint`.
- Tests: `python scripts/ci.py test`.
- Docs: `python scripts/ci.py docs`.
- Packaging: `python scripts/ci.py packaging`.

For feature work, fix failures locally before opening or updating a pull request
to `main`; ordinary feature-branch pushes intentionally have no hosted CI.
