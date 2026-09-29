# Task: ci-testing-release-optimization

**Date:** 2026-09-29
**Role:** Programmer / Architect
**Component:** `scripts/release.py`, `.github/workflows/ci.yml`, `scripts/audit_ci.py`, `tests/`
**Status:** Completed

## 1. Goal

Optimize GitHub Actions CI for credit efficiency on free accounts, enhance release automation (`scripts/release.py`) with auto-bumping and dry-run capabilities, and establish foundational test taxonomy structuring.

## 2. Scope

### In Scope

- **Release Tooling (`scripts/release.py`):**
  - Add `--dry-run` option to `prepare` to preview changelog and `pyproject.toml` edits without file mutations or fragment deletions.
  - Add `--auto` (or `auto` target version argument) to compute the minimum valid SemVer target automatically from pending fragments.
  - Add unit tests in `tests/test_core/test_release_tooling.py` covering `--dry-run` and `--auto`.
- **CI Credit & Runtime Optimization (`.github/workflows/ci.yml`, `scripts/ci.py`, `scripts/audit_ci.py`):**
  - Order cheap static checks (`release.py check`, `ruff check`) before downloading/installing heavy third-party dependencies (`matplotlib`, `cryptography`, etc.).
  - Replace full repository history clone (`fetch-depth: 0`) with shallow clone + shallow tag fetch (`fetch-depth: 1` + `git fetch --tags --depth=1`).
  - Add pytest parallel execution via `pytest-xdist` (`-n auto`) when available to cut runner execution time.
  - Maintain compatibility with `tests/test_core/test_ci_policy.py` and repository contracts.
- **Test Structuring & Taxonomy (`tests/conftest.py`, `pyproject.toml`):**
  - Introduce `tests/conftest.py` with standard markers (`slow`, `integration`, `policy`, `meta`).
  - Register markers in `pyproject.toml` to satisfy `--strict-markers`.
  - Add testing taxonomy guide in `docs/guides/testing-taxonomy.md`.
- **Changelog Fragment:**
  - Add appropriate fragment in `changes/`.

### Out of Scope

- Removing or altering the core package dependency-free guarantee.
- Altering the public API contract of `gunz_utils`.

## 3. Approach

Make atomic, verified changes accompanied by regression and contract tests. Verify with local verification primitives.

## 4. Implementation Steps

1. [x] Update `scripts/release.py` with `--dry-run` and `auto` target resolution.
2. [x] Add unit tests in `tests/test_core/test_release_tooling.py`.
3. [x] Add `tests/conftest.py` and register markers in `pyproject.toml`.
4. [x] Optimize `.github/workflows/ci.yml` and update `tests/test_core/test_ci_policy.py`.
5. [x] Add `--skip-packaging` to `scripts/audit_ci.py` and invoke conditionally in PRs when packaging files are unchanged.
6. [x] Tag contract/policy tests (`@pytest.mark.policy`) and stress/subprocess tests (`@pytest.mark.slow`).
7. [x] Document testing taxonomy guide in `docs/guides/testing-taxonomy.md`.
8. [x] Add changelog fragment in `changes/`.
9. [x] Verify all modified files, test contracts, and run release checks.

## 5. Verification

- [x] `test_ci_policy.py` contract tests passed.
- [x] `test_repository_contracts.py` contract tests passed.
- [x] `test_audit_ci.py` test suite with `--skip-packaging` passed.
- [x] `test_release_tooling.py` strict SemVer, auto resolution, and dry-run tests passed.
- [x] `test_invariants_stress.py` and `test_subprocess.py` unit tests passed.
- [x] `python scripts/release.py status` verified (18 fragments, minor bump to 1.12.0).
- [x] `python scripts/release.py check` verified (OK).
- [x] `python scripts/release.py prepare --dry-run` verified (atomic, no side-effects).


