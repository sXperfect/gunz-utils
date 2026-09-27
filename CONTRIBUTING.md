# Contributing to Gunz Utils

Contributions should keep `gunz-utils` small, reusable, and domain-neutral.
Prefer a shared primitive here only when its contract is useful across multiple
consumers; application policy and framework-specific behavior normally belong
in the consuming repository.

## Development setup

Requirements:

- Python 3.11 or newer.
- Git.
- A local virtual environment or other isolated Python environment.

From a clone of the repository:

```bash
python -m pip install -e ".[all,plot,docs]"
python -m pip install pytest==9.0.2 ruff==0.14.10 mypy==1.19.1
```

The pinned tool versions above mirror `.github/workflows/ci.yml`.

## Change workflow

1. Branch from the current `main`.
2. Keep the change focused and preserve backward compatibility unless an
   intentional breaking change is being prepared.
3. Reuse existing utilities and public abstractions before adding overlapping
   helpers.
4. Add or update tests with the implementation.
5. Update user-facing documentation when behavior, installation, or public APIs
   change.
6. Add a changelog fragment for every user-visible change.
7. Run the canonical local verification gate before merge.

## Verification

Run the same consolidated gate used by the repository tooling:

```bash
./scripts/verify.sh
```

For faster iteration, the individual checks are:

```bash
python scripts/release.py check
python -m ruff check src tests benchmarks scripts
python -m mypy src/gunz_utils
python -m pytest
python scripts/ci.py docs
python scripts/ci.py packaging
```

Python 3.12 compatibility is also exercised by hosted CI for pull requests
targeting `main` and pushes to `main`.

Ruff formatting is configured but is not a repository gate; do not introduce a
separate formatter requirement that conflicts with the checked-in style.

## Changelog fragments

Do not edit the top of `CHANGELOG.md` for ordinary development changes. Add a
small file under [`changes/`](changes/) using the format:

```text
<unique-id>.<category>.md
```

Supported categories and their release impact are documented in
[`changes/README.md`](changes/README.md).

Useful commands:

```bash
python scripts/release.py check
python scripts/release.py status
```

Release preparation is documented in
[`docs/development/releases.md`](docs/development/releases.md).

## Documentation

Keep `README.md` concise and focused on installation, scope, major capabilities,
and navigation. Detailed API and usage documentation belongs under
[`docs/source/`](docs/source/).

Build documentation strictly with:

```bash
./scripts/build_docs.sh
```

The build treats Sphinx warnings as errors.

## Public API and dependencies

The core package is dependency-free. New third-party requirements should be
optional unless there is a strong repository-wide reason to change that policy.

When changing public APIs:

- prefer additive, backward-compatible changes;
- keep namespace behavior intentional;
- preserve historical compatibility aliases when they remain supported;
- document deprecations before removals;
- add focused regression tests for compatibility-sensitive behavior.

## Security and repository hygiene

- Never commit credentials, tokens, private keys, or secret-bearing fixtures.
- Use the redaction helpers for logs and diagnostics that may contain sensitive
  values.
- Do not commit local editor, AI-agent, worktree, deployment, or build caches.
- Keep generated documentation under `docs/_build/` untracked.
- Avoid shell interpolation when `gunz_utils.subprocess` or another structured
  API can express the operation safely.

## Pull requests

Pull requests should target `main` and should explain:

- what changed and why;
- the user-visible or compatibility impact;
- tests and verification performed;
- any follow-up work intentionally left out of scope.

Hosted CI is intentionally limited to pull requests targeting `main` and pushes
to `main`, so feature branches should be verified locally before review.
